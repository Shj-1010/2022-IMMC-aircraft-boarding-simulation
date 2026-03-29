import numpy as np
import random
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from matplotlib.patches import Rectangle

# ==========================================
# 1. 시뮬레이션 환경 및 사용자 정의 변수 설정
# ==========================================
RANDOM_SEED = 42

NUM_ROWS = 47
SEATS_PER_ROW = 7
OCCUPANCY_RATE = 1.0 

SEAT_PITCH = 0.76            
WALKING_SPEED = 0.9          
MIN_DIST = 0.3               
SEAT_INTERFERENCE_TIME = 3.5 
NON_COMPLIANT_RATIO = 0.0    
MISS_SEAT_PROBABILITY = 0.01      

DELTA_EMPTY = 0.5   

PERSONA_TYPES = ['window', 'aisle', 'middle', 'apathetic']
FREE_PERSONA_RATIOS = [0.4, 0.4, 0.1, 0.1] 

BIN_CAPACITY = 12       
CONGESTION_U = 10       
THRESHOLD_K = 0.5       
SEARCH_PENALTY = 15     

BAGGAGE_VOLUMES = {'none': 0, 'backpack': 2, 'carrier': 4, 'hand_bag': 1}
BAGGAGE_ITEMS = {'none': 0, 'backpack': 6.56, 'carrier': 7.13, 'hand_bag': 3.67}

AGE_WEIGHTS = {
    'youth': {'walk_mult': 1.0, 'stow_mult': 1.0, 'extra_stow': {'none': 0, 'backpack': 0, 'carrier': 0, 'hand_bag': 0}},
    'elderly': {'walk_mult': 0.5, 'stow_mult': 1.0, 'extra_stow': {'none': 0, 'backpack': 2.0, 'carrier': 0.5, 'hand_bag': 0.5}}
}

SEAT_Y_MAP = {0: 0, 1: 1, 2: 3, 3: 4, 4: 5, 5: 7, 6: 8}
AISLE_Y_MAP = {0: 2, 1: 6}

# ==========================================
# 2. 승객(Agent) 클래스 및 헬퍼
# ==========================================
def get_seat_type(s):
    if s in [0, 6]: return 'window'
    elif s == 3: return 'middle'
    else: return 'aisle'

def get_adj_seats(s):
    if s == 0: return [1]
    if s == 1: return [0]
    if s == 2: return [3]
    if s == 3: return [2, 4]
    if s == 4: return [3]
    if s == 5: return [6]
    if s == 6: return [5]
    return []

class Passenger:
    def __init__(self, p_id, target_row, target_seat, strategy, baggage_keys, BAGGAGE_RATIO, age_keys, AGE_RATIO, entrance):
        self.id = p_id
        self.target_row = target_row
        self.target_seat = target_seat
        self.entrance = entrance 
        
        self.baggage = np.random.choice(baggage_keys, p=BAGGAGE_RATIO)
        self.age_group = np.random.choice(age_keys, p=AGE_RATIO)
        self.is_compliant = np.random.choice([True, False], p=[1-NON_COMPLIANT_RATIO, NON_COMPLIANT_RATIO])
        self.persona = np.random.choice(PERSONA_TYPES, p=FREE_PERSONA_RATIOS)
        self.walk_speed = WALKING_SPEED * AGE_WEIGHTS[self.age_group]['walk_mult']
        
        if target_row is not None:
            self.real_target_pos_m = target_row * SEAT_PITCH
            self.target_pos_m = self.real_target_pos_m
            self.aisle_idx = 0 if target_seat <= 3 else 1
            
        self.pos_m = 0.0
        self.state = 'waiting'
        self.seating_time_left = 0
        self.stow_time_left = 0 
        self.missed_seat = False
        self.direction = 1 if self.entrance == 'front' else -1
        
        if strategy not in ['ROW', 'FREE'] and target_row is not None:
            if random.random() < MISS_SEAT_PROBABILITY:
                if entrance == 'front' and self.target_row < 24:
                    self.missed_seat = True
                    self.target_pos_m = random.randint(self.target_row + 1, 24) * SEAT_PITCH
                elif entrance == 'rear' and self.target_row > 25:
                    self.missed_seat = True
                    self.target_pos_m = random.randint(25, self.target_row - 1) * SEAT_PITCH

# ==========================================
# 3. 탑승 전략 큐 생성 함수들
# ==========================================
def apply_non_compliance(queue):
    compliant = [p for p in queue if p.is_compliant]
    non_compliant = [p for p in queue if not p.is_compliant]
    for p in non_compliant:
        insert_idx = random.randint(0, len(compliant))
        compliant.insert(insert_idx, p)
    return compliant

def get_random_queue(passengers):
    front = [p for p in passengers if p.entrance == 'front']
    rear = [p for p in passengers if p.entrance == 'rear']
    random.shuffle(front); random.shuffle(rear)
    return apply_non_compliance(front), apply_non_compliance(rear)

def get_zone_queue(passengers):
    A = [p for p in passengers if 0 <= p.target_row <= 11]
    B = [p for p in passengers if 12 <= p.target_row <= 24]
    C = [p for p in passengers if 25 <= p.target_row <= 35]
    D = [p for p in passengers if 36 <= p.target_row <= 46]
    for q in [A, B, C, D]: random.shuffle(q)
    return apply_non_compliance(B + A), apply_non_compliance(C + D)

def get_wilma_queue(passengers):
    front = [p for p in passengers if p.entrance == 'front']
    rear = [p for p in passengers if p.entrance == 'rear']
    def sort_wilma(queue):
        window = [p for p in queue if get_seat_type(p.target_seat) == 'window']
        middle = [p for p in queue if get_seat_type(p.target_seat) == 'middle']
        aisle = [p for p in queue if get_seat_type(p.target_seat) == 'aisle']
        random.shuffle(window); random.shuffle(middle); random.shuffle(aisle)
        return apply_non_compliance(window + middle + aisle)
    return sort_wilma(front), sort_wilma(rear)

def get_row_queue(passengers):
    front_queue, rear_queue = [], []
    for r in range(24, -1, -1):
        row_pax = [p for p in passengers if p.entrance == 'front' and p.target_row == r]
        random.shuffle(row_pax)
        front_queue.extend(row_pax)
    for r in range(25, NUM_ROWS):
        row_pax = [p for p in passengers if p.entrance == 'rear' and p.target_row == r]
        random.shuffle(row_pax)
        rear_queue.extend(row_pax)
    return apply_non_compliance(front_queue), apply_non_compliance(rear_queue)

def get_free_seating_queue(passengers):
    temp_occupied = np.zeros((NUM_ROWS, SEATS_PER_ROW))
    front_pax = [p for p in passengers if p.entrance == 'front']
    rear_pax = [p for p in passengers if p.entrance == 'rear']
    random.shuffle(front_pax); random.shuffle(rear_pax)
    
    # 🌟 버그 수정: 전체 좌석을 하나의 풀로 통합
    avail_seats = [{'row': r, 'seat': s} for r in range(NUM_ROWS) for s in range(SEATS_PER_ROW)]
    
    def assign_seats(pax_list, entrance):
        for p in pax_list:
            best_seats = []; max_P = -1.0
            for seat in avail_seats:
                r, s = seat['row'], seat['seat']
                s_type = get_seat_type(s)
                
                w_type = 1.0
                if p.persona == 'window': w_type = 3.0 if s_type == 'window' else (1.5 if s_type == 'aisle' else 1.0)
                elif p.persona == 'aisle': w_type = 3.0 if s_type == 'aisle' else (1.5 if s_type == 'window' else 1.0)
                elif p.persona == 'middle': w_type = 3.0 if s_type == 'middle' else (1.5 if s_type == 'window' else 1.0)
                
                # 🌟 거리에 따른 가중치 (들어온 문에서 가까울수록 점수가 높음)
                w_row = 1.0
                if entrance == 'front':
                    w_row = 1.0 + (NUM_ROWS - r) / NUM_ROWS 
                else:
                    w_row = 1.0 + r / NUM_ROWS
                
                n_empty_adj = sum(1 for adj_s in get_adj_seats(s) if temp_occupied[r, adj_s] == 0)
                w_empty = 1.0 + DELTA_EMPTY * n_empty_adj
                p_i = w_type * w_row * w_empty
                
                if p_i > max_P: max_P = p_i; best_seats = [seat]
                elif p_i == max_P: best_seats.append(seat)
            
            chosen_seat = random.choice(best_seats)
            p.target_row, p.target_seat = chosen_seat['row'], chosen_seat['seat']
            p.real_target_pos_m = p.target_row * SEAT_PITCH
            p.target_pos_m = p.real_target_pos_m 
            p.aisle_idx = 0 if p.target_seat <= 3 else 1
            temp_occupied[p.target_row, p.target_seat] = 1
            avail_seats.remove(chosen_seat)

    # 양쪽 문 승객들이 번갈아가며 자리를 고르도록 (공평하게)
    max_len = max(len(front_pax), len(rear_pax))
    for i in range(max_len):
        if i < len(front_pax): assign_seats([front_pax[i]], 'front')
        if i < len(rear_pax): assign_seats([rear_pax[i]], 'rear')
        
    return apply_non_compliance(front_pax), apply_non_compliance(rear_pax)

# ==========================================
# 4. 시뮬레이션 제너레이터 
# ==========================================
def simulation_generator(strategy):
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    
    baggage_keys = list(BAGGAGE_ITEMS.keys())
    age_keys = list(AGE_WEIGHTS.keys())
    
    BAGGAGE_RATIO = np.random.rand(len(baggage_keys)); BAGGAGE_RATIO /= BAGGAGE_RATIO.sum()
    AGE_RATIO = np.random.rand(len(age_keys)); AGE_RATIO /= AGE_RATIO.sum()

    all_seats = [(r, s) for r in range(NUM_ROWS) for s in range(SEATS_PER_ROW)]
    num_passengers = int(len(all_seats) * OCCUPANCY_RATE)
    selected_seats = random.sample(all_seats, num_passengers) if OCCUPANCY_RATE < 1.0 else all_seats

    passengers = []
    for i, (r, s) in enumerate(selected_seats):
        entrance = 'front' if r <= 24 else 'rear'
        if strategy == 'FREE':
            r, s = None, None 
            entrance = 'front' if i % 2 == 0 else 'rear'
        passengers.append(Passenger(i, r, s, strategy, baggage_keys, BAGGAGE_RATIO, age_keys, AGE_RATIO, entrance))

    if strategy == 'RANDOM': front_q, rear_q = get_random_queue(passengers)
    elif strategy == 'ZONE': front_q, rear_q = get_zone_queue(passengers)
    elif strategy == 'WILMA': front_q, rear_q = get_wilma_queue(passengers)
    elif strategy == 'ROW': front_q, rear_q = get_row_queue(passengers)
    elif strategy == 'FREE': front_q, rear_q = get_free_seating_queue(passengers)

    aisles = {0: [], 1: []} 
    seating_passengers = [] 
    seated_matrix = np.zeros((NUM_ROWS, SEATS_PER_ROW))
    overhead_bins = [{'left': BIN_CAPACITY, 'center': BIN_CAPACITY, 'right': BIN_CAPACITY} for _ in range(NUM_ROWS)]
    
    time_ticks = 0

    def start_stowing(p):
        p.state = 'stowing'
        p.direction = 0 
        v_o = BAGGAGE_VOLUMES[p.baggage]
        if v_o == 0:
            p.stow_time_left = 0
            return
        target_side = 'left' if p.target_seat <= 1 else ('center' if p.target_seat <= 4 else 'right')
        v_e = overhead_bins[p.target_row][target_side]
        alpha = SEARCH_PENALTY if v_e < v_o else 0
        overhead_bins[p.target_row][target_side] -= v_o
        exp_val = np.exp(-CONGESTION_U * ((v_o / max(1, v_e)) - THRESHOLD_K))
        p.stow_time_left = max(1, int((alpha + (BAGGAGE_ITEMS[p.baggage] / (1 + exp_val))) * AGE_WEIGHTS[p.age_group]['stow_mult'] + AGE_WEIGHTS[p.age_group]['extra_stow'][p.baggage]))

    while not all(p.state == 'seated' for p in passengers):
        time_ticks += 1
        
        for p in seating_passengers[:]:
            p.seating_time_left -= 1
            if p.seating_time_left <= 0:
                p.state = 'seated'
                seated_matrix[p.target_row, p.target_seat] = 1
                seating_passengers.remove(p)

        for a_idx in [0, 1]:
            for p in aisles[a_idx]:
                if p.state == 'stowing':
                    p.stow_time_left -= 1
                    if p.stow_time_left <= 0:
                        p.state = 'seating'
                        blocks = 0
                        if p.target_seat == 0 and seated_matrix[p.target_row, 1] != 0: blocks = 1
                        if p.target_seat == 3 and seated_matrix[p.target_row, 2] != 0: blocks = 1
                        if p.target_seat == 6 and seated_matrix[p.target_row, 5] != 0: blocks = 1
                        p.seating_time_left = blocks * SEAT_INTERFERENCE_TIME
                        seating_passengers.append(p)
            aisles[a_idx][:] = [p for p in aisles[a_idx] if p.state in ['walking', 'stowing']]

        for a_idx in [0, 1]:
            aisles[a_idx].sort(key=lambda x: x.pos_m)
            for i, p in enumerate(aisles[a_idx]):
                if p.state == 'walking':
                    if p.direction == 1:
                        blocking_p = next((other for other in aisles[a_idx][i+1:] if other.direction in [0, 1]), None)
                        max_pos = blocking_p.pos_m - MIN_DIST if blocking_p else float('inf')
                        p.pos_m = min(p.pos_m + p.walk_speed, max_pos, p.target_pos_m)
                        if p.pos_m == p.target_pos_m:
                            if p.missed_seat: p.missed_seat = False; p.target_pos_m = p.real_target_pos_m; p.direction = -1
                            else: start_stowing(p)
                    elif p.direction == -1:
                        blocking_p = next((other for other in reversed(aisles[a_idx][:i]) if other.direction in [0, -1]), None)
                        min_pos = blocking_p.pos_m + MIN_DIST if blocking_p else float('-inf')
                        p.pos_m = max(p.pos_m - p.walk_speed, min_pos, p.target_pos_m)
                        if p.pos_m == p.target_pos_m:
                            if p.missed_seat: p.missed_seat = False; p.target_pos_m = p.real_target_pos_m; p.direction = 1
                            else: start_stowing(p)

        if front_q:
            if not any(p.pos_m < MIN_DIST for p in aisles[front_q[0].aisle_idx]):
                p = front_q.pop(0); p.state = 'walking'; p.pos_m = 0.0
                aisles[p.aisle_idx].append(p)
        if rear_q:
            rear_start_pos = (NUM_ROWS - 1) * SEAT_PITCH
            if not any(p.pos_m > rear_start_pos - MIN_DIST for p in aisles[rear_q[0].aisle_idx]):
                p = rear_q.pop(0); p.state = 'walking'; p.pos_m = rear_start_pos
                aisles[p.aisle_idx].append(p)

        frame_data = {
            'ticks': time_ticks,
            'seated': np.copy(seated_matrix),
            'active_pax': []
        }
        for a_idx in [0, 1]:
            for p in aisles[a_idx]:
                row_idx = p.pos_m / SEAT_PITCH 
                frame_data['active_pax'].append((row_idx, AISLE_Y_MAP[a_idx], p.state))
        for p in seating_passengers:
            frame_data['active_pax'].append((p.target_row, SEAT_Y_MAP[p.target_seat], p.state))
            
        yield frame_data

# ==========================================
# 5. 애니메이션 렌더링
# ==========================================
def run_animation(strategy):
    print(f"🎬 '{strategy}' 전략 시각화 준비 중... (가로 모드, 부드러운 속도)")
    
    fig, ax = plt.subplots(figsize=(16, 5))
    ax.set_title(f"Boarding Strategy: {strategy} (Twin-Door, 2-3-2)", fontsize=14, fontweight='bold')
    ax.set_xlim(-2, NUM_ROWS + 1)
    ax.set_ylim(-1, 9)
    ax.invert_yaxis() 
    ax.axis('off')

    ax.text(-1, 4, '⬅️ Front Door', ha='right', va='center', fontweight='bold', color='gray')
    ax.text(NUM_ROWS, 4, 'Rear Door ➡️', ha='left', va='center', fontweight='bold', color='gray')

    colors = {'walking': 'green', 'stowing': 'orange', 'seating': 'red', 'seated': 'dodgerblue'}
    for state, color in colors.items():
        ax.scatter([], [], c=color, label=state.capitalize(), s=50)
    ax.legend(loc='upper right', bbox_to_anchor=(1.0, 1.15), ncol=4)

    for r in range(NUM_ROWS):
        for s in range(SEATS_PER_ROW):
            ax.add_patch(Rectangle((r-0.4, SEAT_Y_MAP[s]-0.4), 0.8, 0.8, color='lightgray', alpha=0.5))

    scat_seated = ax.scatter([], [], c=colors['seated'], s=35, marker='s')
    scat_active = ax.scatter([], [], c=[], s=50, edgecolors='black', linewidth=0.5)
    time_text = ax.text(0.01, 1.05, '', transform=ax.transAxes, fontsize=12, fontweight='bold')

    def update(frame):
        seated_r, seated_c = np.where(frame['seated'] == 1) 
        if len(seated_r) > 0:
            seated_y = [SEAT_Y_MAP[c] for c in seated_c]
            scat_seated.set_offsets(np.c_[seated_r, seated_y]) 

        if frame['active_pax']:
            xs, ys, states = zip(*frame['active_pax']) 
            c = [colors[s] for s in states]
            scat_active.set_offsets(np.c_[xs, ys])
            scat_active.set_color(c)
        else:
            scat_active.set_offsets(np.empty((0, 2)))

        mins, secs = frame['ticks'] // 60, frame['ticks'] % 60
        time_text.set_text(f"Time: {mins:02d}m {secs:02d}s")
        return scat_seated, scat_active, time_text

    sim_gen = simulation_generator(strategy)
    ani = animation.FuncAnimation(fig, update, frames=sim_gen, interval=20, blit=False, repeat=False)
    plt.tight_layout()
    plt.show()

if __name__ == "__main__":
    # ========================================================
    # RANDOM, ZONE, WILMA, ROW, FREE
    # ========================================================
    SELECTED_STRATEGY = 'ROW' 
    
    run_animation(SELECTED_STRATEGY)