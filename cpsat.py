import time
import math
from ortools.sat.python import cp_model

class ScalableCPSatSudokuSolver:
    def __init__(self, grid_size=9):
        """
        :param grid_size: Board dimension N x N (must be a perfect square: 9, 16, 25, etc.)
        """
        self.N = grid_size
        self.sub_n = int(math.isqrt(grid_size))
        if self.sub_n * self.sub_n != grid_size:
            raise ValueError(f"Grid size {grid_size} must be a perfect square (e.g., 9, 16, 25).")

    def solve(self, board, time_limit=None, num_workers=0):
        """
        Solves the given board using Google OR-Tools CP-SAT and tracks metrics.
        :param board: 2D list representation of Sudoku grid (0 represents empty cells)
        :param time_limit: Time limit in seconds for the solver
        :param num_workers: Number of CPU threads to allocate (0 uses all available cores)
        :return: (solution, stats_dict)
        """
        model_start = time.time()
        model = cp_model.CpModel()

        # 1. Decision Variables: x[r, c] in {1, ..., N}
        x = {}
        for r in range(self.N):
            for c in range(self.N):
                x[r, c] = model.NewIntVar(1, self.N, f"x_{r}_{c}")

        # 2. Row Constraints: All elements in a row must be distinct
        for r in range(self.N):
            model.AddAllDifferent([x[r, c] for c in range(self.N)])

        # 3. Column Constraints: All elements in a column must be distinct
        for c in range(self.N):
            model.AddAllDifferent([x[r, c] for r in range(self.N)])

        # 4. Subgrid Constraints: All elements in each subgrid block must be distinct
        for sr in range(0, self.N, self.sub_n):
            for sc in range(0, self.N, self.sub_n):
                subgrid_vars = [
                    x[sr + r, sc + c]
                    for r in range(self.sub_n)
                    for c in range(self.sub_n)
                ]
                model.AddAllDifferent(subgrid_vars)

        # 5. Fix given clues
        num_clues = 0
        for r in range(self.N):
            for c in range(self.N):
                val = board[r][c]
                if val != 0:
                    model.Add(x[r, c] == val)
                    num_clues += 1

        model_building_time = time.time() - model_start

        # Configure Solver parameters
        solver = cp_model.CpSolver()
        if time_limit is not None:
            solver.parameters.max_time_in_seconds = float(time_limit)
        
        # Configure multi-threading
        if num_workers > 0:
            solver.parameters.num_search_workers = num_workers

        # Solve model
        solve_start = time.time()
        status = solver.Solve(model)
        solve_time = time.time() - solve_start
        total_time = time.time() - model_start

        is_sat = (status == cp_model.OPTIMAL or status == cp_model.FEASIBLE)

        stats = {
            "grid_size": f"{self.N}x{self.N}",
            "num_vars": self.N * self.N,
            "num_clues": num_clues,
            "model_time": round(model_building_time, 5),
            "solve_time": round(solve_time, 5),
            "total_time": round(total_time, 5),
            "status": "SAT" if is_sat else "UNSAT/TIMEOUT",
            "branches": solver.NumBranches(),
            "conflicts": solver.NumConflicts()
        }

        if is_sat:
            solution = [[0] * self.N for _ in range(self.N)]
            for r in range(self.N):
                for c in range(self.N):
                    solution[r][c] = solver.Value(x[r, c])
            return solution, stats
        else:
            return None, stats


# --- BENCHMARKING SCRIPT FOR LARGER BOARDS ---
def run_cpsat_benchmark():
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

    print("=" * 105)
    print(f"{'BOARD':<8} | {'VARS':<8} | {'CLUES':<8} | {'SOLVE TIME (s)':<15} | {'TOTAL TIME (s)':<15} | {'CONFLICTS':<10} | {'STATUS':<10}")
    print("=" * 105)

    for name, board in puzzles:
        grid_size = len(board)
        try:
            solver = ScalableCPSatSudokuSolver(grid_size=grid_size)
            sol, stats = solver.solve(board, time_limit=60)
            
            print(f"{stats['grid_size']:<8} | {stats['num_vars']:<8} | {stats['num_clues']:<8} | "
                  f"{stats['solve_time']:<15.5f} | {stats['total_time']:<15.5f} | {stats['conflicts']:<10} | {stats['status']:<10}")
        except Exception as e:
            print(f"{name:<8} | ERROR: {e}")

    print("=" * 105)

if __name__ == "__main__":
    run_cpsat_benchmark()