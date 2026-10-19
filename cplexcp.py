import time
import math
from docplex.cp.model import CpoModel

class ScalableCplexCPSudokuSolver:
    def __init__(self, grid_size=9):
        self.N = grid_size
        self.sub_n = int(math.isqrt(grid_size))
        if self.sub_n * self.sub_n != grid_size:
            raise ValueError(f"Grid size {grid_size} must be a perfect square (e.g., 9, 16, 25).")

    def solve(self, board, time_limit=None, log_output=False):
        """
        Solves the given board and tracks execution/search metrics.
        :param board: 2D list representation of Sudoku grid (0 represents empty cells)
        :param time_limit: Time limit in seconds for the solver
        :param log_output: Set to True to display CPLEX CP search logs
        :return: (solution, stats_dict)
        """
        model_start = time.time()
        mdl = CpoModel(name=f"Sudoku_CP_{self.N}x{self.N}")
        cp_path = "/opt/ibm/ILOG/CPLEX_Studio222/cpoptimizer/bin/x86-64_linux/cpoptimizer"
        # 1. Decision Variables: x[r][c] in {1, ..., N}
        x = [[mdl.integer_var(1, self.N, name=f"x_{r}_{c}") 
              for c in range(self.N)] 
             for r in range(self.N)]

        # 2. Row Constraints: All cells in a row must be distinct
        for r in range(self.N):
            mdl.add(mdl.all_diff(x[r]))

        # 3. Column Constraints: All cells in a column must be distinct
        for c in range(self.N):
            mdl.add(mdl.all_diff([x[r][c] for r in range(self.N)]))

        # 4. Subgrid Constraints: All cells in each subgrid block must be distinct
        for sr in range(0, self.N, self.sub_n):
            for sc in range(0, self.N, self.sub_n):
                subgrid_vars = [
                    x[sr + r][sc + c]
                    for r in range(self.sub_n)
                    for c in range(self.sub_n)
                ]
                mdl.add(mdl.all_diff(subgrid_vars))

        # 5. Fix given clues
        num_clues = 0
        for r in range(self.N):
            for c in range(self.N):
                val = board[r][c]
                if val != 0:
                    mdl.add(x[r][c] == val)
                    num_clues += 1

        model_building_time = time.time() - model_start

        """
        # Configure solver parameters
        if time_limit is not None:
            mdl.set_time_limit(time_limit)
        """
        solve_start = time.time()
        res = mdl.solve(LogVerbosity='Verbose' if log_output else 'Quiet')
        solve_time = time.time() - solve_start
        total_time = time.time() - model_start

        stats = {
            "grid_size": f"{self.N}x{self.N}",
            "num_vars": self.N * self.N,
            "num_clues": num_clues,
            "model_time": round(model_building_time, 5),
            "solve_time": round(solve_time, 5),
            "total_time": round(total_time, 5),
            "status": "SAT" if res else "UNSAT/TIMEOUT"
        }

        if res:
            solution = [[0] * self.N for _ in range(self.N)]
            for r in range(self.N):
                for c in range(self.N):
                    solution[r][c] = res.get_value(x[r][c])
            return solution, stats
        else:
            return None, stats


# benchmark
def run_cplex_cp_benchmark():
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

    # Empty boards to test constraint propagation and search scaling
    puzzles = [
        ("9x9", generate_empty_board(9)),
        ("16x16", generate_empty_board(16)),
        ("25x25", generate_empty_board(25))
    ]

    print("=" * 85)
    print(f"{'BOARD':<8} | {'VARS':<8} | {'CLUES':<8} | {'SOLVE TIME (s)':<15} | {'TOTAL TIME (s)':<15} | {'STATUS':<10}")
    print("=" * 85)

    for name, board in puzzles:
        grid_size = len(board)
        try:
            solver = ScalableCplexCPSudokuSolver(grid_size=grid_size)
            sol, stats = solver.solve(board, time_limit=60)
            
            print(f"{stats['grid_size']:<8} | {stats['num_vars']:<8} | {stats['num_clues']:<8} | "
                  f"{stats['solve_time']:<15.5f} | {stats['total_time']:<15.5f} | {stats['status']:<10}")
        except Exception as e:
            print(f"{name:<8} | ERROR: {e}")

    print("=" * 85)

if __name__ == "__main__":
    run_cplex_cp_benchmark()