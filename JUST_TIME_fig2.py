import numpy as np
import random
import time

# ==========================================
# 1. 시뮬레이션 환경 및 BWB 기체 구조 설정
# ==========================================
RANDOM_SEED = 132
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

NUM_ROWS = 14
NUM_COLS = 24

WALKING_SPEED = 0.5
MIN_DIST = 1.0
SEAT_INTERFERENCE_TIME = 3.5

# [수납 관련 변수]
BAGGAGE_ITEMS = {'none': 0, 'backpack': 6.56, 'carrier': 7.13, 'hand_bag': 3.67}
AGE_WEIGHTS = {
    'youth': {'walk_mult': 1.0, 'stow_mult': 1.0},
    'elderly': {'walk_mult': 0.5, 'stow_mult': 1.0}
}
baggage_keys = list(BAGGAGE_ITEMS.keys())
age_keys = list(AGE_WEIGHTS.keys())
BAGGAGE_RATIO = np.random.rand(len(baggage_keys)); BAGGAGE_RATIO /= BAGGAGE_RATIO.sum()
AGE_RATIO = np.random.rand(len(age_keys)); AGE_RATIO /= AGE_RATIO.sum()

# ==========================================
# 2. 기체 좌표 및 좌석 로직
# ==========================================
def is_valid_seat(r, c):
    if r < 3 and (c < 3 or c > 20): return False
    return True

def get_aisle_x(c):
    if c <= 5: return 3   # 통로 1
    if c <= 11: return 10 # 통로 2
    if c <= 17: return 17 # 통로 3
    return 24             # 통로 4

def get_blocks(r, c, matrix):
    if c <= 2: return sum(1 for x in matrix[r, c+1:3] if x != 0)
    elif c <= 5: return sum(1 for x in matrix[r, 3:c] if x != 0)
    elif c <= 8: return sum(1 for x in matrix[r, c+1:9] if x != 0)
    elif c <= 11: return sum(1 for x in matrix[r, 9:c] if x != 0)
    elif c <= 14: return sum(1 for x in matrix[r, c+1:15] if x != 0)
    elif c <= 17: return sum(1 for x in matrix[r, 15:c] if x != 0)
    elif c <= 20: return sum(1 for x in matrix[r, c+1:21] if x != 0)
    else: return sum(1 for x in matrix[r, 21:c] if x != 0)

# ==========================================
# 3. 승객(Agent) 클래스
# ==========================================
class Passenger:
    def __init__(self, p_id, r, c):
        self.id = p_id
        self.target_row = r
        self.target_col = c
        self.target_aisle_x = get_aisle_x(c)
        self.target_y = r + 1 
        
        self.baggage = np.random.choice(baggage_keys, p=BAGGAGE_RATIO)
        self.age_group = np.random.choice(age_keys, p=AGE_RATIO)
        self.walk_speed = WALKING_SPEED * AGE_WEIGHTS[self.age_group]['walk_mult']
        
        self.pos_x = -1.0 
        self.pos_y = 0.0  
        self.state = 'waiting' 
        self.stow_time_left = 0
        self.seating_time_left = 0

# ==========================================
# 4. 탑승 큐(Queue) 생성 함수
# ==========================================
def get_wilma_priority(c):
    if c in [0, 5, 6, 11, 12, 17, 18, 23]: return 1
    elif c in [1, 4, 7, 10, 13, 16, 19, 22]: return 2
    elif c in [2, 3, 8, 9, 14, 15, 20, 21]: return 3
    return 3

def get_queue(passengers, strategy):
    queue = passengers.copy()
    
    if strategy == 'RANDOM':
        random.shuffle(queue)
        
    elif strategy == 'ZONE':
        z1 = [p for p in queue if 11 <= p.target_row <= 13]
        z2 = [p for p in queue if 8 <= p.target_row <= 10]
        z3 = [p for p in queue if 5 <= p.target_row <= 7]
        z4 = [p for p in queue if 2 <= p.target_row <= 4]
        z5 = [p for p in queue if 0 <= p.target_row <= 1]
        for z in [z1, z2, z3, z4, z5]: random.shuffle(z)
        queue = z1 + z2 + z3 + z4 + z5
        
    elif strategy == 'WILMA':
        prio1 = [p for p in queue if get_wilma_priority(p.target_col) == 1]
        prio2 = [p for p in queue if get_wilma_priority(p.target_col) == 2]
        prio3 = [p for p in queue if get_wilma_priority(p.target_col) == 3]
        for p_list in [prio1, prio2, prio3]: random.shuffle(p_list)
        queue = prio1 + prio2 + prio3
        
    elif strategy == 'ROW':
        queue.sort(key=lambda p: (-p.target_row, random.random()))
        
    return queue

# ==========================================
# 5. 메인 시뮬레이션 엔진 (애니메이션 제거)
# ==========================================
def run_simulation(strategy):
    # 매번 동일한 결과를 피하기 위해 내부에서 승객 초기화
    passengers = [Passenger(i, r, c) for i, (r, c) in enumerate((r, c) for r in range(NUM_ROWS) for c in range(NUM_COLS) if is_valid_seat(r, c))]
    boarding_queue = get_queue(passengers, strategy)
    
    active_passengers = [] 
    seated_matrix = np.zeros((NUM_ROWS, NUM_COLS), dtype=int)
    time_ticks = 0
    
    # 큐에 남은 사람이 있거나 아직 자리에 덜 앉은 사람이 있으면 계속 실행
    while len(boarding_queue) > 0 or len(active_passengers) > 0:
        time_ticks += 1

        # 1. 착석 및 짐 수납 처리
        for p in active_passengers[:]:
            if p.state == 'seating':
                p.seating_time_left -= 1
                if p.seating_time_left <= 0:
                    p.state = 'seated'
                    seated_matrix[p.target_row, p.target_col] = 1 # 착석 완료 표시
                    active_passengers.remove(p)
                    
            elif p.state == 'stowing':
                p.stow_time_left -= 1
                if p.stow_time_left <= 0:
                    p.state = 'seating'
                    blocks = get_blocks(p.target_row, p.target_col, seated_matrix)
                    p.seating_time_left = blocks * SEAT_INTERFERENCE_TIME

        # 2. 이동 (세로 통로 -> 가로 통로)
        pass_v = [p for p in active_passengers if p.state == 'walking_v']
        pass_v.sort(key=lambda p: p.pos_y, reverse=True)
        
        for p in pass_v:
            blocking = [op for op in pass_v if op.target_aisle_x == p.target_aisle_x and op.pos_y > p.pos_y]
            stowing_p = [op for op in active_passengers if op.state in ['stowing', 'seating'] and op.target_aisle_x == p.target_aisle_x and op.target_y >= p.pos_y]
            
            min_y = float('inf')
            if blocking: min_y = min(min_y, min(op.pos_y for op in blocking) - MIN_DIST)
            if stowing_p: min_y = min(min_y, min(op.target_y for op in stowing_p) - MIN_DIST)
            
            p.pos_y = min(p.pos_y + p.walk_speed, p.target_y, min_y)
            
            if p.pos_y == p.target_y:
                p.state = 'stowing'
                p.stow_time_left = int(BAGGAGE_ITEMS[p.baggage] / 2) + 1 

        pass_h = [p for p in active_passengers if p.state == 'walking_h']
        pass_h.sort(key=lambda p: p.pos_x, reverse=True)
        
        for p in pass_h:
            blocking = [op for op in pass_h if op.pos_x > p.pos_x]
            min_x = float('inf')
            if blocking: min_x = min(min_x, min(op.pos_x for op in blocking) - MIN_DIST)
            
            p.pos_x = min(p.pos_x + p.walk_speed, p.target_aisle_x, min_x)
            
            if p.pos_x == p.target_aisle_x:
                blocking_v = [op for op in active_passengers if op.state in ['walking_v', 'stowing'] and op.target_aisle_x == p.target_aisle_x and op.pos_y < MIN_DIST]
                if not blocking_v:
                    p.state = 'walking_v'

        # 3. 새로운 승객 입장
        if boarding_queue:
            entry_clear = True
            for op in pass_h:
                if op.pos_x < MIN_DIST:
                    entry_clear = False
                    break
            if entry_clear:
                nxt = boarding_queue.pop(0)
                nxt.state = 'walking_h'
                active_passengers.append(nxt)

    return time_ticks

# ==========================================
# 6. 실행 및 결과 비교
# ==========================================
if __name__ == "__main__":
    strategies = ['RANDOM', 'ZONE', 'WILMA', 'ROW']
    
    print("✈️ Multi-Aisle BWB 탑승 시뮬레이션 시작...\n")
    start_time = time.time()
    
    for st in strategies:
        ticks = run_simulation(st)
        print(f"✅ 전략: {st:<8} | 총 탑승 시간(Ticks): {ticks}")
        
    print(f"\n완료! (연산 소요 시간: {time.time() - start_time:.2f}초)")