import time
import math
from pysat.solvers import Solver
from pysat.card import CardEnc, EncType

class ScalablePySatSudokuSolver:
    def __init__(self, grid_size=9, enc_type=EncType.pairwise):
        self.N = grid_size
        self.sub_n = int(math.isqrt(grid_size))
        if self.sub_n * self.sub_n != grid_size:
            raise ValueError(f"Kích thước {grid_size} phải là số chính phương.")
            
        self.enc_type = enc_type
        self.max_var_id = self.N * self.N * self.N
        self.clause_count = 0  # Bộ đếm clause thủ công

    def var_id(self, r, c, v):
        return (r * self.N * self.N) + (c * self.N) + (v + 1)

    def decode_var(self, var_id):
        var_id -= 1
        v = var_id % self.N
        var_id //= self.N
        c = var_id % self.N
        r = var_id // self.N
        return r, c, v + 1

    def new_aux_var(self):
        self.max_var_id += 1
        return self.max_var_id

    def add_clause(self, solver, clause):
        """Hàm bọc (wrapper) để vừa thêm clause vào solver vừa đếm số clause."""
        solver.add_clause(clause)
        self.clause_count += 1

    #commander
    def add_commander_amo(self, solver, lits, group_size=3):
        if len(lits) <= 1:
            return
        if len(lits) <= group_size:
            for i in range(len(lits)):
                for j in range(i + 1, len(lits)):
                    self.add_clause(solver, [-lits[i], -lits[j]])
            return

        groups = [lits[i:i + group_size] for i in range(0, len(lits), group_size)]
        commanders = []

        for group in groups:
            cmd_var = self.new_aux_var()
            commanders.append(cmd_var)
            
            for lit in group:
                self.add_clause(solver, [-cmd_var, lit])
            
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    self.add_clause(solver, [-group[i], -group[j]])

        self.add_commander_amo(solver, commanders, group_size)

    #product
    def add_product_amo(self, solver, lits):
        n = len(lits)
        if n <= 1:
            return
        if n <= 3:
            for i in range(n):
                for j in range(i + 1, n):
                    self.add_clause(solver, [-lits[i], -lits[j]])
            return

        p = int(math.ceil(math.sqrt(n)))
        q = int(math.ceil(n / p))

        row_vars = [self.new_aux_var() for _ in range(p)]
        col_vars = [self.new_aux_var() for _ in range(q)]

        for i in range(p):
            for j in range(i + 1, p):
                self.add_clause(solver, [-row_vars[i], -row_vars[j]])
        for i in range(q):
            for j in range(i + 1, q):
                self.add_clause(solver, [-col_vars[i], -col_vars[j]])

        for idx, lit in enumerate(lits):
            r = idx // q
            c = idx % q
            self.add_clause(solver, [-lit, row_vars[r]])
            self.add_clause(solver, [-lit, col_vars[c]])

    def apply_amo(self, solver, lits):
        if self.enc_type == "commander":
            self.add_commander_amo(solver, lits)
        elif self.enc_type == "product":
            self.add_product_amo(solver, lits)
        else:
            amo_cnf = CardEnc.atmost(lits=lits, bound=1, encoding=self.enc_type)
            for clause in amo_cnf.clauses:
                self.add_clause(solver, clause)

    def encode_rules(self, solver):
        # 1. Cell Constraints
        for r in range(self.N):
            for c in range(self.N):
                lits = [self.var_id(r, c, v) for v in range(self.N)]
                self.add_clause(solver, lits)  # ALO
                self.apply_amo(solver, lits)  # AMO

        # 2. Row Constraints
        for r in range(self.N):
            for v in range(self.N):
                lits = [self.var_id(r, c, v) for c in range(self.N)]
                self.add_clause(solver, lits)
                self.apply_amo(solver, lits)

        # 3. Column Constraints
        for c in range(self.N):
            for v in range(self.N):
                lits = [self.var_id(r, c, v) for r in range(self.N)]
                self.add_clause(solver, lits)
                self.apply_amo(solver, lits)

        # 4. Subgrid Constraints
        for sr in range(0, self.N, self.sub_n):
            for sc in range(0, self.N, self.sub_n):
                for v in range(self.N):
                    lits = [
                        self.var_id(sr + r, sc + c, v)
                        for r in range(self.sub_n)
                        for c in range(self.sub_n)
                    ]
                    self.add_clause(solver, lits)
                    self.apply_amo(solver, lits)


    def solve(self, board, solver_name="kissat"):
        start_time = time.time()
        self.clause_count = 0 
        
        with Solver(name=solver_name) as solver:
            self.encode_rules(solver)

            for r in range(self.N):
                for c in range(self.N):
                    val = board[r][c]
                    if val != 0:
                        self.add_clause(solver, [self.var_id(r, c, val - 1)])

            encoding_time = time.time() - start_time

            num_vars = self.max_var_id
            num_clauses = self.clause_count

            solve_start = time.time()
            is_sat = solver.solve()
            solve_time = time.time() - solve_start
            total_time = time.time() - start_time

            stats = {
                "grid_size": f"{self.N}x{self.N}",
                "num_vars": num_vars,
                "num_clauses": num_clauses,
                "encoding_time": round(encoding_time, 5),
                "solve_time": round(solve_time, 5),
                "total_time": round(total_time, 5),
                "is_sat": is_sat
            }

            if is_sat:
                model = solver.get_model()
                solution = [[0] * self.N for _ in range(self.N)]
                for var in model:
                    if 0 < var <= (self.N * self.N * self.N):
                        r, c, val = self.decode_var(var)
                        if 0 <= r < self.N and 0 <= c < self.N:
                            solution[r][c] = val
                return solution, stats
            else:
                return None, stats

# --- KỊCH BẢN BENCHMARK TỰ ĐỘNG ---
def run_scaling_benchmark():
    def generate_empty_board(N):
        return [[0] * N for _ in range(N)]

    
    """
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
    """
    
    puzzles = [
        ("9x9", generate_empty_board(9)),
        ("16x16", generate_empty_board(16)),
        ("25x25", generate_empty_board(25))
    ]
    
    encodings = [
        ("Pairwise", EncType.pairwise)
        
    ]

    print("=" * 80)
    print(f"{'BOARD':<8} | {'ENCODING':<12} | {'VARS':<8} | {'CLAUSES':<10} | {'SOLVE TIME (s)':<14} | {'TOTAL TIME (s)':<14}")
    print("=" * 80)

    for name, board in puzzles:
        grid_size = len(board)
        for enc_name, enc_type in encodings:
            solver = ScalablePySatSudokuSolver(grid_size=grid_size, enc_type=enc_type)
            
            """
            Cadical300
            Glucose42
            Kissat404
            Minisat22
            """
            sol, stats = solver.solve(board, solver_name="Kissat404")
            
            print(f"{stats['grid_size']:<8} | {enc_name:<12} | {stats['num_vars']:<8} | {stats['num_clauses']:<10} | {stats['solve_time']:<14.5f} | {stats['total_time']:<14.5f}")

    print("=" * 80)

if __name__ == "__main__":
    run_scaling_benchmark()