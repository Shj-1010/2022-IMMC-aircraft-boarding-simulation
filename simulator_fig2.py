import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import random

# ==========================================
# 1. 시뮬레이션 환경 및 BWB 기체 구조 설정
# ==========================================
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# [수정됨: 기체 행 수 14행으로 확장]
NUM_ROWS = 14  # 앞뒤로 1~14행 (인덱스 0~13)
NUM_COLS = 24  # 좌우로 1~24열 (인덱스 0~23)

# 'RANDOM', 'ZONE', 'WILMA', 'ROW', 'FREE' 중 택 1
BOARDING_STRATEGY = 'ZONE' 

WALKING_SPEED = 0.5          
MIN_DIST = 1.0               
SEAT_INTERFERENCE_TIME = 3.5 
NON_COMPLIANT_RATIO = 0.0    

# --- [자유좌석제 전용 변수] ---
PERSONA_TYPES = ['window', 'aisle', 'middle', 'apathetic']
FREE_PERSONA_RATIOS = [0.4, 0.4, 0.1, 0.1]
PERSONA_COLORS = {'window': 'cyan', 'aisle': 'pink', 'middle': 'lightgreen', 'apathetic': 'dimgray'}

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
    # 1~3행(r < 3)일 때, 1~3열(c < 3)과 22~24열(c > 20)은 좌석 없음
    if r < 3 and (c < 3 or c > 20):
        return False
    return True

def get_vis_x(c):
    if c <= 2: return c
    if c <= 5: return c + 1
    if c <= 8: return c + 1
    if c <= 11: return c + 2
    if c <= 14: return c + 2
    if c <= 17: return c + 3
    if c <= 20: return c + 3
    return c + 4

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
        self.persona = np.random.choice(PERSONA_TYPES, p=FREE_PERSONA_RATIOS)
        self.walk_speed = WALKING_SPEED * AGE_WEIGHTS[self.age_group]['walk_mult']
        
        self.pos_x = -1.0 
        self.pos_y = 0.0  
        self.state = 'waiting' 
        self.stow_time_left = 0
        self.seating_time_left = 0

# ==========================================
# 4. [수정됨] 탑승 큐(Queue) 생성 함수 (핵심 로직 변경)
# ==========================================
def get_wilma_priority(c):
    # 우선순위 1: 가장 안쪽 자리 (양끝 블록의 창가 및 중앙 블록의 정중앙)
    if c in [0, 5, 6, 11, 12, 17, 18, 23]: return 1
    # 우선순위 2: 중간 자리
    elif c in [1, 4, 7, 10, 13, 16, 19, 22]: return 2
    # 우선순위 3: 통로 쪽 자리
    elif c in [2, 3, 8, 9, 14, 15, 20, 21]: return 3
    return 3

def get_queue(passengers):
    queue = passengers.copy()
    
    if BOARDING_STRATEGY == 'RANDOM':
        random.shuffle(queue)
        
    elif BOARDING_STRATEGY == 'ZONE':
        # 구역별 분할 (인덱스는 0부터 시작하므로 행 번호에서 -1)
        z1 = [p for p in queue if 11 <= p.target_row <= 13] # 12~14행
        z2 = [p for p in queue if 8 <= p.target_row <= 10]  # 9~11행
        z3 = [p for p in queue if 5 <= p.target_row <= 7]   # 6~8행
        z4 = [p for p in queue if 2 <= p.target_row <= 4]   # 3~5행
        z5 = [p for p in queue if 0 <= p.target_row <= 1]   # 1~2행
        
        # 각 구역 내에서는 무작위 탑승
        for z in [z1, z2, z3, z4, z5]: random.shuffle(z)
        queue = z1 + z2 + z3 + z4 + z5 # 뒤에서부터 탑승
        
    elif BOARDING_STRATEGY == 'WILMA':
        # BWB 맞춤형 안쪽->바깥쪽 탑승
        prio1 = [p for p in queue if get_wilma_priority(p.target_col) == 1]
        prio2 = [p for p in queue if get_wilma_priority(p.target_col) == 2]
        prio3 = [p for p in queue if get_wilma_priority(p.target_col) == 3]
        
        for p_list in [prio1, prio2, prio3]: random.shuffle(p_list)
        queue = prio1 + prio2 + prio3
        
    elif BOARDING_STRATEGY == 'ROW':
        # 행 별로 뒤에서부터 탑승. 같은 행 안에서는 랜덤
        queue.sort(key=lambda p: (-p.target_row, random.random()))
        
    return queue

# ==========================================
# 5. 초기화 및 메인 시뮬레이션
# ==========================================
passengers = [Passenger(i, r, c) for i, (r, c) in enumerate((r, c) for r in range(NUM_ROWS) for c in range(NUM_COLS) if is_valid_seat(r, c))]
boarding_queue = get_queue(passengers)

active_passengers = [] 
seated_matrix = np.zeros((NUM_ROWS, NUM_COLS), dtype=object)
time_ticks = 0

# 시각화 Y축 크기를 14행에 맞게 조절
fig, ax = plt.subplots(figsize=(16, 9))

def update(frame):
    global time_ticks
    
    # 🌟 [수정 핵심]: 로직을 4번 돌리고 화면은 1번만 그리도록 묶음 (4배속 효과)
    for _ in range(4):
        if all(p.state == 'seated' for p in passengers):
            ax.set_title(f"[{BOARDING_STRATEGY}] BWB Boarding Complete! Total Time: {time_ticks} sec")
            return
            
        time_ticks += 1

        # 1. 착석 및 짐 수납 처리 (기존과 동일)
        for p in active_passengers[:]:
            if p.state == 'seating':
                p.seating_time_left -= 1
                if p.seating_time_left <= 0:
                    p.state = 'seated'
                    seated_matrix[p.target_row, p.target_col] = p.persona
                    active_passengers.remove(p)
                    
            elif p.state == 'stowing':
                p.stow_time_left -= 1
                if p.stow_time_left <= 0:
                    p.state = 'seating'
                    blocks = get_blocks(p.target_row, p.target_col, seated_matrix)
                    p.seating_time_left = blocks * SEAT_INTERFERENCE_TIME

        # 2. 이동 (세로 통로 -> 가로 통로) (기존과 동일)
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

        # 3. 새로운 승객 입장 (기존과 동일)
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

    # ================= 렌더링 (for문 밖에서 1번만 실행) =================
    ax.clear()
    ax.set_xlim(-2, 29)
    ax.set_ylim(15, -1.5) 
    
    title_text = f"[{BOARDING_STRATEGY}] Multi-Aisle BWB | Time: {time_ticks} sec"
    ax.set_title(title_text)
    ax.axis('off')

    ax.axhspan(-1.0, 0.5, facecolor='whitesmoke', edgecolor='none')
    for x in [3, 10, 17, 24]:
        ax.axvspan(x - 0.3, x + 0.3, ymin=0, ymax=14, facecolor='whitesmoke', edgecolor='none')

    for r in range(NUM_ROWS):
        for c in range(NUM_COLS):
            if not is_valid_seat(r, c): continue
            vis_x = get_vis_x(c)
            y_pos = r + 1
            seat_val = seated_matrix[r, c]
            
            color = 'lightgray'
            if seat_val != 0:
                color = PERSONA_COLORS.get(seat_val, 'blue') if BOARDING_STRATEGY == 'FREE' else 'blue'
            ax.plot(vis_x, y_pos, 's', color=color, markersize=7)

    for p in active_passengers:
        color = 'red' if p.state == 'walking_h' else ('orange' if p.state == 'walking_v' else 'green')
        if p.state == 'walking_h':
            ax.plot(p.pos_x, p.pos_y, 'o', color=color, markersize=5)
        elif p.state in ['walking_v', 'stowing', 'seating']:
            ax.plot(p.target_aisle_x, p.pos_y, 'o', color=color, markersize=5)

ani = animation.FuncAnimation(fig, update, frames=1000, interval=20, repeat=False)
plt.show()