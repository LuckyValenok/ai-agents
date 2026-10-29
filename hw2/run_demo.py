"""Выполняет memory_agent.ipynb как две отдельные сессии в двух процессах ядра.

    uv run hw2/run_demo.py

Ядро 1: код + раздел «Первый запуск».
Ядро 2 (новый процесс): код + «После перезапуска» + «Несколько профилей».
Так в сохранённом ноутбуке видно, что факты пережили настоящий перезапуск.
"""
from pathlib import Path

import nbformat
from nbclient import NotebookClient

HERE = Path(__file__).resolve().parent
NOTEBOOK = HERE / "memory_agent.ipynb"
PHASES = [{"setup", "session1"}, {"setup", "session2", "profiles"}]


def main() -> None:
    nb = nbformat.read(NOTEBOOK, as_version=4)
    client = NotebookClient(nb, timeout=900, kernel_name="python3", resources={"metadata": {"path": str(HERE)}})
    for n, tags in enumerate(PHASES, 1):
        with client.setup_kernel():
            for index, cell in enumerate(nb.cells):
                if cell.cell_type == "code" and tags & set(cell.metadata.get("tags", [])):
                    client.execute_cell(cell, index)
        print(f"ядро {n}: выполнено")
    nbformat.write(nb, NOTEBOOK)
    print(f"сохранено: {NOTEBOOK}")


if __name__ == "__main__":
    main()
