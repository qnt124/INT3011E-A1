import time
import math
import os
import subprocess
import tempfile
from docplex.mp.model import Model

class ScalableCplexMIPSudokuSolver:
    def __init__(self, grid_size=9, cplex_exec_path="/opt/ibm/ILOG/CPLEX_Studio222/cplex/bin/x86-64_linux/cplex"):
        """
        :param grid_size: Board dimension N x N (must be a perfect square: 9, 16, 25, etc.)
        :param cplex_exec_path: Path to the CPLEX Interactive Solver executable
        """
        self.N = grid_size
        self.sub_n = int(math.isqrt(grid_size))
        if self.sub_n * self.sub_n != grid_size:
            raise ValueError(f"Grid size {grid_size} must be a perfect square (e.g., 9, 16, 25).")
        self.cplex_exec_path = cplex_exec_path

    def parse_solution_file(self, sol_filepath):
        """Parses the solution values from the written .sol file."""
        solution = [[0] * self.N for _ in range(self.N)]
        if not os.path.exists(sol_filepath):
            return None

        with open(sol_filepath, 'r') as f:
            for line in f:
                if 'name="x_' in line and 'value="' in line:
                    try:
                        # Extract variable name and value e.g. name="x_0_0_4" value="1"
                        var_part = line.split('name="x_')[1].split('"')[0]
                        val_part = float(line.split('value="')[1].split('"')[0])
                        
                        if val_part > 0.5:
                            r, c, k = map(int, var_part.split('_'))
                            solution[r][c] = k + 1
                    except (IndexError, ValueError):
                        continue
        return solution

    def solve(self, board, time_limit=None, log_output=False):
        """
        Solves the given board using Option B (docplex export to .lp + CPLEX CLI) and tracks metrics.
        :param board: 2D list representation of Sudoku grid (0 represents empty cells)
        :param time_limit: Time limit in seconds for the solver
        :param log_output: Set to True to display CPLEX solver logs
        :return: (solution, stats_dict)
        """
        model_start = time.time()
        mdl = Model(name=f"Sudoku_MIP_{self.N}x{self.N}")
        
        # 1. Decision Variables: x[r, c, k] = 1 if cell (r, c) contains digit k + 1
        x = mdl.binary_var_dict(
            [(r, c, k) for r in range(self.N) for c in range(self.N) for k in range(self.N)],
            name="x"
        )

        # 2. Cell Constraints: Each cell (r, c) must contain EXACTLY ONE value
        for r in range(self.N):
            for c in range(self.N):
                mdl.add_constraint(
                    mdl.sum(x[r, c, k] for k in range(self.N)) == 1,
                    ctname=f"cell_{r}_{c}"
                )

        # 3. Row Constraints: Each row r must contain digit k EXACTLY ONCE
        for r in range(self.N):
            for k in range(self.N):
                mdl.add_constraint(
                    mdl.sum(x[r, c, k] for c in range(self.N)) == 1,
                    ctname=f"row_{r}_{k}"
                )

        # 4. Column Constraints: Each column c must contain digit k EXACTLY ONCE
        for c in range(self.N):
            for k in range(self.N):
                mdl.add_constraint(
                    mdl.sum(x[r, c, k] for r in range(self.N)) == 1,
                    ctname=f"col_{c}_{k}"
                )

        # 5. Subgrid Constraints: Each subgrid block must contain digit k EXACTLY ONCE
        for sr in range(0, self.N, self.sub_n):
            for sc in range(0, self.N, self.sub_n):
                for k in range(self.N):
                    mdl.add_constraint(
                        mdl.sum(
                            x[sr + r, sc + c, k]
                            for r in range(self.sub_n)
                            for c in range(self.sub_n)
                        ) == 1,
                        ctname=f"subgrid_{sr}_{sc}_{k}"
                    )

        # 6. Fix given clues
        num_clues = 0
        for r in range(self.N):
            for c in range(self.N):
                val = board[r][c]
                if val != 0:
                    mdl.add_constraint(x[r, c, val - 1] == 1, ctname=f"clue_{r}_{c}")
                    num_clues += 1

        model_building_time = time.time() - model_start

        # Option B Execution: Write LP file and invoke CPLEX CLI
        with tempfile.TemporaryDirectory() as temp_dir:
            lp_path = os.path.join(temp_dir, "sudoku.lp")
            sol_path = os.path.join(temp_dir, "sudoku.sol")
            
            mdl.export_as_lp(lp_path)

            # Build CPLEX CLI command string
            cplex_cmds = [f'read "{lp_path}"']
            if time_limit is not None:
                cplex_cmds.append(f'set timelimit {time_limit}')
            cplex_cmds.append('optimize')
            cplex_cmds.append(f'write "{sol_path}"')
            cplex_cmds.append('quit')

            cplex_input = "\n".join(cplex_cmds) + "\n"

            solve_start = time.time()
            process = subprocess.run(
                [self.cplex_exec_path],
                input=cplex_input,
                text=True,
                capture_output=not log_output
            )
            solve_time = time.time() - solve_start
            total_time = time.time() - model_start

            solution = self.parse_solution_file(sol_path)
            is_sat = solution is not None

        stats = {
            "grid_size": f"{self.N}x{self.N}",
            "num_vars": self.N ** 3,
            "num_constraints": len(list(mdl.iter_constraints())),
            "num_clues": num_clues,
            "model_time": round(model_building_time, 5),
            "solve_time": round(solve_time, 5),
            "total_time": round(total_time, 5),
            "status": "SAT" if is_sat else "UNSAT/TIMEOUT"
        }

        return solution, stats


# --- BENCHMARKING SCRIPT FOR LARGER BOARDS ---
def run_cplex_mip_benchmark():
    def generate_empty_board(N):
        return [[0] * N for _ in range(N)]

    # Sample 9x9 Board
    puzzle_9x9 = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],
        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],
        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9]
    ]

    puzzles = [
        ("9x9", generate_empty_board(9)),
        ("16x16", generate_empty_board(16)),
        ("25x25", generate_empty_board(25))
    ]

    print("=" * 95)
    print(f"{'BOARD':<8} | {'VARS':<8} | {'CONSTRS':<8} | {'CLUES':<8} | {'SOLVE TIME (s)':<15} | {'TOTAL TIME (s)':<15} | {'STATUS':<10}")
    print("=" * 95)

    for name, board in puzzles:
        grid_size = len(board)
        try:
            solver = ScalableCplexMIPSudokuSolver(grid_size=grid_size)
            sol, stats = solver.solve(board, time_limit=60)
            
            print(f"{stats['grid_size']:<8} | {stats['num_vars']:<8} | {stats['num_constraints']:<8} | "
                  f"{stats['num_clues']:<8} | {stats['solve_time']:<15.5f} | {stats['total_time']:<15.5f} | {stats['status']:<10}")
        except Exception as e:
            print(f"{name:<8} | ERROR: {e}")

    print("=" * 95)

if __name__ == "__main__":
    run_cplex_mip_benchmark()