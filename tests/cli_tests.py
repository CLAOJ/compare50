import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ORIGINAL_C = """#include <stdio.h>

int total_score(int scores[], int count)
{
    int total = 0;
    for (int i = 0; i < count; i++)
    {
        total += scores[i];
    }
    return total;
}

float average_score(int scores[], int count)
{
    if (count == 0)
    {
        return 0.0;
    }
    return (float) total_score(scores, count) / count;
}

int highest_score(int scores[], int count)
{
    int best = scores[0];
    for (int i = 1; i < count; i++)
    {
        if (scores[i] > best)
        {
            best = scores[i];
        }
    }
    return best;
}

int lowest_score(int scores[], int count)
{
    int worst = scores[0];
    for (int i = 1; i < count; i++)
    {
        if (scores[i] < worst)
        {
            worst = scores[i];
        }
    }
    return worst;
}

void print_report(int scores[], int count)
{
    printf("Total: %d\\n", total_score(scores, count));
    printf("Average: %.2f\\n", average_score(scores, count));
    printf("Highest: %d\\n", highest_score(scores, count));
    printf("Lowest: %d\\n", lowest_score(scores, count));
}

int main(void)
{
    int scores[] = {72, 88, 95, 61, 79, 84, 90, 67};
    int count = sizeof(scores) / sizeof(scores[0]);
    print_report(scores, count);
    return 0;
}
"""

RENAMES = {
    "total_score": "sum_values",
    "average_score": "mean_value",
    "highest_score": "max_value",
    "lowest_score": "min_value",
    "print_report": "show_summary",
    "scores": "values",
    "count": "n",
    "total": "acc",
    "best": "top",
    "worst": "bottom",
}

UNRELATED_CPP = """#include <iostream>
#include <string>
#include <vector>

struct Cell
{
    char mark;
    bool played;
};

class Board
{
public:
    Board() : cells(9, Cell{'.', false}) {}

    bool place(int pos, char who)
    {
        if (pos < 0 || pos >= 9 || cells[pos].played)
        {
            return false;
        }
        cells[pos].mark = who;
        cells[pos].played = true;
        return true;
    }

    char winner() const
    {
        static const int lines[8][3] = {
            {0, 1, 2}, {3, 4, 5}, {6, 7, 8},
            {0, 3, 6}, {1, 4, 7}, {2, 5, 8},
            {0, 4, 8}, {2, 4, 6}
        };
        for (const auto &line : lines)
        {
            char a = cells[line[0]].mark;
            if (a != '.' && a == cells[line[1]].mark && a == cells[line[2]].mark)
            {
                return a;
            }
        }
        return '.';
    }

    void show() const
    {
        for (int row = 0; row < 3; row++)
        {
            for (int col = 0; col < 3; col++)
            {
                std::cout << cells[row * 3 + col].mark;
            }
            std::cout << std::endl;
        }
    }

private:
    std::vector<Cell> cells;
};

int main()
{
    Board board;
    std::string moves = "XOXOXOXXO";
    char who = 'X';
    for (char c : moves)
    {
        board.place(c - '0', who);
        who = (who == 'X') ? 'O' : 'X';
    }
    board.show();
    std::cout << "Winner: " << board.winner() << std::endl;
    return 0;
}
"""

PAYLOAD = "</script><script>alert(1)</script>"


def rename(source):
    pattern = re.compile(r"\b(" + "|".join(sorted(RENAMES, key=len, reverse=True)) + r")\b")
    return pattern.sub(lambda m: RENAMES[m.group(1)], source)


def run_compare50(cwd, *args):
    return subprocess.run(
        [sys.executable, "-m", "compare50", *args],
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        encoding="utf8",
        timeout=600,
    )


def read_graph(index_html):
    for line in index_html.splitlines():
        if "GRAPH = " in line:
            return json.loads(line.split("GRAPH = ", 1)[1].rstrip().rstrip(";"))
    raise AssertionError("no GRAPH line in index.html")


class TestCompare50Cli(unittest.TestCase):
    def setUp(self):
        self.working_directory = tempfile.TemporaryDirectory()
        self.cwd = self.working_directory.name

    def tearDown(self):
        self.working_directory.cleanup()

    def write(self, path, content):
        full = os.path.join(self.cwd, path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf8") as f:
            f.write(content)

    def test_ranks_copied_pair_first(self):
        self.write("a/main.cpp", ORIGINAL_C)
        self.write("b/main.cpp", rename(ORIGINAL_C))
        self.write("c/main.cpp", UNRELATED_CPP)

        result = run_compare50(self.cwd, "a", "b", "c", "-o", "out", "-n", "3")

        self.assertEqual(result.returncode, 0, result.stderr)
        index = os.path.join(self.cwd, "out", "index.html")
        self.assertTrue(os.path.isfile(index))
        with open(index, encoding="utf8") as f:
            links = read_graph(f.read())["links"]
        first = links[0]
        self.assertEqual({os.path.basename(first["source"]), os.path.basename(first["target"])}, {"a", "b"})

    def test_pages_do_not_embed_webfonts(self):
        # Every page inlines its CSS; the 440 KB base64 webfonts made each report page ~0.6-0.9 MB.
        self.write("a/main.cpp", ORIGINAL_C)
        self.write("b/main.cpp", rename(ORIGINAL_C))

        result = run_compare50(self.cwd, "a", "b", "-o", "out", "-n", "3")

        self.assertEqual(result.returncode, 0, result.stderr)
        for page in ("index.html", "match_1.html"):
            path = os.path.join(self.cwd, "out", page)
            with open(path, encoding="utf8") as f:
                self.assertFalse("@font-face" in f.read(), page)
            self.assertLess(os.path.getsize(path), 450_000, page)

    def test_match_page_has_syntax_colours(self):
        self.write("a/main.cpp", ORIGINAL_C)
        self.write("b/main.cpp", rename(ORIGINAL_C))

        result = run_compare50(self.cwd, "a", "b", "-o", "out", "-n", "3")

        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(self.cwd, "out", "match_1.html"), encoding="utf8") as f:
            page = f.read()
        self.assertIn('<span class="tk-k">return</span>', page)
        # Line numbers still come from code.newline: one per source line, per side, per pass
        newlines = page.count('class="line newline"')
        self.assertGreater(newlines, 0)
        self.assertEqual(newlines % (2 * ORIGINAL_C.count("\n")), 0)

    def test_escapes_source_and_names(self):
        # Windows filenames cannot contain < or >, so use other HTML metacharacters there
        name = "x&b;y" if os.name == "nt" else "x<b>y"
        source = ORIGINAL_C + f"\n/* {PAYLOAD} */\n"
        self.write(f"{name}/main.c", source)
        self.write("z/main.c", source)

        result = run_compare50(self.cwd, name, "z", "-o", "out", "-n", "5")

        self.assertEqual(result.returncode, 0, result.stderr)
        out = os.path.join(self.cwd, "out")
        html_files = [os.path.join(out, f) for f in os.listdir(out) if f.endswith(".html")]
        self.assertTrue(html_files)
        for path in html_files:
            with open(path, encoding="utf8") as f:
                content = f.read()
            self.assertNotIn(PAYLOAD, content, path)
            self.assertNotIn(name, content, path)

    def test_imports_without_lib50(self):
        code = "import sys; sys.modules['lib50'] = None; import compare50.__main__"
        result = subprocess.run([sys.executable, "-c", code], cwd=ROOT,
                                capture_output=True, text=True, encoding="utf8", timeout=120)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_no_network_call(self):
        # Every DNS lookup and socket connect fails and leaves a marker on stderr
        code = ("import socket, sys\n"
                "def _deny(*args, **kwargs):\n"
                "    sys.stderr.write('NETWORK ATTEMPT\\n')\n"
                "    raise OSError('network disabled for test')\n"
                "socket.getaddrinfo = _deny\n"
                "socket.socket.connect = _deny\n"
                "socket.create_connection = _deny\n"
                "sys.argv = ['compare50', 'a', 'b', '-o', 'out', '-n', '3']\n"
                "import runpy\n"
                "runpy.run_module('compare50', run_name='__main__', alter_sys=True)\n")
        self.write("a/main.cpp", ORIGINAL_C)
        self.write("b/main.cpp", rename(ORIGINAL_C))
        result = subprocess.run([sys.executable, "-c", code], cwd=self.cwd, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding="utf8", timeout=600)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("NETWORK ATTEMPT", result.stderr)

    def test_hashes_agree_across_processes(self):
        # Pool workers are spawned with a fresh hash seed on Windows and macOS, so k-gram hashes must not depend on it
        code = ("import types; from compare50.comparators._winnowing import ScoreIndex; "
                "toks = [types.SimpleNamespace(val=v) for v in 'int main ( void ) { return 0 ; }'.split()]; "
                "print(sorted(ScoreIndex(3, 4).hashes(toks)))")
        outputs = []
        for seed in ("1", "2"):
            result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env={**os.environ, "PYTHONHASHSEED": seed},
                                    capture_output=True, text=True, encoding="utf8", timeout=120)
            self.assertEqual(result.returncode, 0, result.stderr)
            outputs.append(result.stdout)
        self.assertEqual(outputs[0], outputs[1])


if __name__ == "__main__":
    unittest.main()
