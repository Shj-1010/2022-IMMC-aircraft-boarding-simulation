import numpy as np
import random
import time

# ==========================================
# 1. 시뮬레이션 환경 및 사용자 정의 변수 설정
# ==========================================
RANDOM_SEED = 132

NUM_ROWS = 33
SEATS_PER_ROW = 6

# [추가된 변수: 탑승률 조절 (0.0 ~ 1.0)]
OCCUPANCY_RATE = 1.0 

# [추가된 변수: 짐 과다 상황 변수 (0: 일반 상황, 1: 모두 캐리어 소지)]
HEAVY_LUGGAGE_SCENARIO = 1

SEAT_PITCH = 0.76            
WALKING_SPEED = 0.9          
MIN_DIST = 0.3               
SEAT_INTERFERENCE_TIME = 3.5 
NON_COMPLIANT_RATIO = 0.0    

# [빌런(지정석을 지나치는 승객) 관련 변수]
MISS_SEAT_PROBABILITY = 0.01      
COLLISION_SPEED_MULTIPLIER = 0.70   

# --- [자유좌석제 전용 변수 및 페르소나 비율] ---
ALPHA_DIST = 0.02  
BETA_COMP = 0.5    
DELTA_EMPTY = 0.5   # 옆자리가 비어있을 때의 가중치 (\delta)

PERSONA_TYPES = ['window', 'aisle', 'middle', 'apathetic']
FREE_PERSONA_RATIOS = [0.4, 0.4, 0.1, 0.1] # 창가 선호(40%), 통로 선호(40%), 중간 선호(10%), 무신경(10%)

# [부피 및 점프 효과 관련 변수]
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

# ==========================================
# 2. 승객(Agent) 클래스 정의
# ==========================================
class Passenger:
    def __init__(self, p_id, target_row, target_seat, strategy, baggage_keys, BAGGAGE_RATIO, age_keys, AGE_RATIO):
        self.id = p_id
        self.target_row = target_row
        self.target_seat = target_seat
        self.real_target_pos_m = target_row * SEAT_PITCH
        self.target_pos_m = self.real_target_pos_m
        
        self.baggage = np.random.choice(baggage_keys, p=BAGGAGE_RATIO)
        self.age_group = np.random.choice(age_keys, p=AGE_RATIO)
        self.is_compliant = np.random.choice([True, False], p=[1-NON_COMPLIANT_RATIO, NON_COMPLIANT_RATIO])
        
        self.persona = np.random.choice(PERSONA_TYPES, p=FREE_PERSONA_RATIOS)
        
        self.walk_speed = WALKING_SPEED * AGE_WEIGHTS[self.age_group]['walk_mult']
        
        self.pos_m = 0.0
        self.state = 'waiting'
        self.seating_time_left = 0
        self.stow_time_left = 0 
        
        self.missed_seat = False
        self.returning = False
        self.direction = 1 
        
        if strategy not in ['ROW', 'FREE']:
            if random.random() < MISS_SEAT_PROBABILITY:
                if strategy in ['RANDOM', 'WILMA']:
                    if self.target_row < NUM_ROWS - 1:
                        self.missed_seat = True
                        false_row = random.randint(self.target_row + 1, NUM_ROWS - 1)
                        self.target_pos_m = false_row * SEAT_PITCH
                        
                elif strategy == 'ZONE':
                    if self.target_row <= 10:     zone_max = 10
                    elif self.target_row <= 21:   zone_max = 21
                    else:                         zone_max = 32
                    
                    if self.target_row < zone_max:
                        self.missed_seat = True
                        false_row = random.randint(self.target_row + 1, zone_max)
                        self.target_pos_m = false_row * SEAT_PITCH

# ==========================================
# 3. 탑승 전략 (Boarding Strategies) 정의
# ==========================================
def apply_non_compliance(queue):
    compliant = [p for p in queue if p.is_compliant]
    non_compliant = [p for p in queue if not p.is_compliant]
    for p in non_compliant:
        insert_idx = random.randint(0, len(compliant))
        compliant.insert(insert_idx, p)
    return compliant

def get_random_queue(passengers):
    queue = passengers.copy()
    random.shuffle(queue)
    return apply_non_compliance(queue)

def get_zone_queue(passengers):
    back = [p for p in passengers if 22 <= p.target_row <= 32]
    middle = [p for p in passengers if 11 <= p.target_row <= 21]
    front = [p for p in passengers if 0 <= p.target_row <= 10]
    random.shuffle(back); random.shuffle(middle); random.shuffle(front)
    return apply_non_compliance(back + middle + front)

def get_wilma_queue(passengers):
    window = [p for p in passengers if p.target_seat in [0, 5]]
    middle = [p for p in passengers if p.target_seat in [1, 4]]
    aisle = [p for p in passengers if p.target_seat in [2, 3]]
    random.shuffle(window); random.shuffle(middle); random.shuffle(aisle)
    return apply_non_compliance(window + middle + aisle)

def get_row_queue(passengers):
    queue = []
    for r in range(NUM_ROWS - 1, -1, -1):
        row_pax = [p for p in passengers if p.target_row == r]
        random.shuffle(row_pax) 
        queue.extend(row_pax)
    return apply_non_compliance(queue)

def get_free_seating_queue(passengers):
    queue = passengers.copy()
    random.shuffle(queue) 
    
    available_seats = [{'row': r, 'seat': s} for r in range(NUM_ROWS) for s in range(SEATS_PER_ROW)]
    
    def get_seat_type(s):
        if s in [0, 5]: return 'window'
        elif s in [1, 4]: return 'middle'
        else: return 'aisle'
        
    def get_adj_seats(s):
        if s == 0: return [1]
        elif s == 1: return [0, 2]
        elif s == 2: return [1]
        elif s == 3: return [4]
        elif s == 4: return [3, 5]
        elif s == 5: return [4]
        return []

    temp_occupied = np.zeros((NUM_ROWS, SEATS_PER_ROW))
    
    for i, p in enumerate(queue):
        best_seats = []
        max_P = -1.0
        
        for seat in available_seats:
            r, s = seat['row'], seat['seat']
            s_type = get_seat_type(s)
            
            w_type = 1.0
            if p.persona == 'window':
                w_type = 3.0 if s_type == 'window' else (1.5 if s_type == 'aisle' else 1.0)
            elif p.persona == 'aisle':
                w_type = 3.0 if s_type == 'aisle' else (1.5 if s_type == 'window' else 1.0)
            elif p.persona == 'middle':
                w_type = 3.0 if s_type == 'middle' else (1.5 if s_type == 'window' else 1.0)
            elif p.persona == 'apathetic':
                w_type = 1.0
            
            w_row = 2.0 if (r == 0 or r == NUM_ROWS - 1) else 1.0
            
            adj_seats = get_adj_seats(s)
            n_empty_adj = sum(1 for adj_s in adj_seats if temp_occupied[r, adj_s] == 0)
            w_empty = 1.0 + DELTA_EMPTY * n_empty_adj
            
            p_i = w_type * w_row * w_empty
            
            if p_i > max_P:
                max_P = p_i
                best_seats = [seat]
            elif p_i == max_P:
                best_seats.append(seat)
        
        chosen_seat = random.choice(best_seats)
        chosen_r, chosen_s = chosen_seat['row'], chosen_seat['seat']
        chosen_type = get_seat_type(chosen_s)
        
        s_left = sum(1 for seat in available_seats if get_seat_type(seat['seat']) == chosen_type)
        
        p.target_row = chosen_r
        p.target_seat = chosen_s
        p.real_target_pos_m = p.target_row * SEAT_PITCH
        p.target_pos_m = p.real_target_pos_m 
        
        temp_occupied[chosen_r, chosen_s] = 1
        available_seats.remove(chosen_seat)
        
        v_0 = p.walk_speed             
        d = chosen_r + 1           
        speed_multiplier = np.exp(ALPHA_DIST * d + BETA_COMP * (max_P / (s_left + 1)))
        p.walk_speed = v_0 * speed_multiplier

    return apply_non_compliance(queue)

# ==========================================
# 4. 시뮬레이션 실행 함수 (반복 실행 구조)
# ==========================================
def run_simulation(strategy):
    start_time = time.time()
    
    # 전략별로 완벽히 동일한 초기 조건을 생성하기 위해 시드 리셋
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)
    
    def generate_random_ratios(num_categories):
        ratios = np.random.rand(num_categories)
        return ratios / ratios.sum()

    baggage_keys = list(BAGGAGE_ITEMS.keys())
    age_keys = list(AGE_WEIGHTS.keys())
    
    # 🌟 [수정된 부분]: 짐 과다 상황 처리
    if HEAVY_LUGGAGE_SCENARIO == 1:
        # 무조건 carrier만 선택되도록 확률 설정 (순서: 'none', 'backpack', 'carrier', 'hand_bag')
        BAGGAGE_RATIO = np.array([0.0, 0.0, 1.0, 0.0])
    else:
        BAGGAGE_RATIO = generate_random_ratios(len(baggage_keys))
        
    AGE_RATIO = generate_random_ratios(len(age_keys))

    all_seats = [(r, s) for r in range(NUM_ROWS) for s in range(SEATS_PER_ROW)]
    num_passengers = int(len(all_seats) * OCCUPANCY_RATE)
    
    # OCCUPANCY_RATE가 1.0 미만일 때만 random.sample을 호출하여 시드 오염 방지
    if OCCUPANCY_RATE < 1.0:
        selected_seats = random.sample(all_seats, num_passengers)
    else:
        selected_seats = all_seats

    passengers = [Passenger(i, r, s, strategy, baggage_keys, BAGGAGE_RATIO, age_keys, AGE_RATIO) 
                  for i, (r, s) in enumerate(selected_seats)]

    if strategy == 'RANDOM': boarding_queue = get_random_queue(passengers)
    elif strategy == 'ZONE': boarding_queue = get_zone_queue(passengers)
    elif strategy == 'WILMA': boarding_queue = get_wilma_queue(passengers)
    elif strategy == 'ROW': boarding_queue = get_row_queue(passengers)
    elif strategy == 'FREE': boarding_queue = get_free_seating_queue(passengers)

    aisle_passengers = [] 
    seating_passengers = [] 
    seated_matrix = np.zeros((NUM_ROWS, SEATS_PER_ROW), dtype=object)
    overhead_bins = [{'left': BIN_CAPACITY, 'right': BIN_CAPACITY} for _ in range(NUM_ROWS)]
    time_ticks = 0

    def start_stowing(p):
        p.state = 'stowing'
        p.direction = 0 
        v_o = BAGGAGE_VOLUMES[p.baggage]
        if v_o == 0:
            p.stow_time_left = 0
        else:
            target_side = 'left' if p.target_seat < 3 else 'right'
            v_e = overhead_bins[p.target_row][target_side]
            alpha = 0
            
            if v_e < v_o:
                alpha = SEARCH_PENALTY
                found = False
                for offset in range(1, NUM_ROWS):
                    for side in ['left', 'right']:
                        r_back = p.target_row + offset
                        if r_back < NUM_ROWS and overhead_bins[r_back][side] >= v_o:
                            v_e = overhead_bins[r_back][side]
                            overhead_bins[r_back][side] -= v_o
                            found = True; break
                        r_front = p.target_row - offset
                        if r_front >= 0 and overhead_bins[r_front][side] >= v_o:
                            v_e = overhead_bins[r_front][side]
                            overhead_bins[r_front][side] -= v_o
                            found = True; break
                    if found: break
                if not found:
                    v_e = v_o 
            else:
                overhead_bins[p.target_row][target_side] -= v_o
            
            t_0 = BAGGAGE_ITEMS[p.baggage]
            exp_val = np.exp(-CONGESTION_U * ((v_o / v_e) - THRESHOLD_K))
            base_time = alpha + (t_0 / (1 + exp_val))
            
            stow_mult = AGE_WEIGHTS[p.age_group]['stow_mult']
            extra_stow = AGE_WEIGHTS[p.age_group]['extra_stow'][p.baggage]
            p.stow_time_left = max(1, int(base_time * stow_mult + extra_stow))

    while not all(p.state == 'seated' for p in passengers):
        time_ticks += 1
        
        for p in seating_passengers[:]:
            p.seating_time_left -= 1
            if p.seating_time_left <= 0:
                p.state = 'seated'
                seated_matrix[p.target_row, p.target_seat] = p.persona
                seating_passengers.remove(p)

        for p in aisle_passengers:
            if p.state == 'stowing':
                p.stow_time_left -= 1
                if p.stow_time_left <= 0:
                    p.state = 'seating'
                    blocks = 0
                    if p.target_seat < 3:
                        blocks = sum(1 for x in seated_matrix[p.target_row, p.target_seat + 1 : 3] if x != 0)
                    else:
                        blocks = sum(1 for x in seated_matrix[p.target_row, 3 : p.target_seat] if x != 0)
                    p.seating_time_left = blocks * SEAT_INTERFERENCE_TIME
                    seating_passengers.append(p)

        aisle_passengers[:] = [p for p in aisle_passengers if p.state in ['walking', 'stowing']]

        for p in aisle_passengers:
            if p.state == 'walking':
                p.direction = -1 if p.returning else 1
            else:
                p.direction = 0 

        aisle_passengers.sort(key=lambda x: x.pos_m, reverse=True)

        for i, p in enumerate(aisle_passengers):
            if p.state == 'walking':
                
                speed_mult = 1.0
                for other in aisle_passengers:
                    if other != p and other.state == 'walking' and other.direction != p.direction:
                        if abs(other.pos_m - p.pos_m) < SEAT_PITCH:
                            speed_mult = COLLISION_SPEED_MULTIPLIER
                            break

                current_speed = p.walk_speed * speed_mult

                if p.direction == 1:
                    blocking_p = None
                    for j in range(i-1, -1, -1):
                        if aisle_passengers[j].direction in [0, 1]:
                            blocking_p = aisle_passengers[j]
                            break
                    
                    max_pos = blocking_p.pos_m - MIN_DIST if blocking_p else float('inf')
                    new_pos = p.pos_m + current_speed * 1 
                    p.pos_m = min(new_pos, max_pos, p.target_pos_m)
                    
                    if p.pos_m == p.target_pos_m:
                        if p.missed_seat:
                            p.missed_seat = False
                            p.returning = True
                            p.target_pos_m = p.real_target_pos_m
                        else:
                            start_stowing(p)

                elif p.direction == -1:
                    blocking_p = None
                    for j in range(i+1, len(aisle_passengers)):
                        if aisle_passengers[j].direction in [0, -1]:
                            blocking_p = aisle_passengers[j]
                            break
                    
                    min_pos = blocking_p.pos_m + MIN_DIST if blocking_p else float('-inf')
                    new_pos = p.pos_m - current_speed * 1
                    p.pos_m = max(new_pos, min_pos, p.target_pos_m)

                    if p.pos_m == p.target_pos_m:
                        p.returning = False
                        start_stowing(p)

        if boarding_queue:
            if not aisle_passengers or aisle_passengers[-1].pos_m >= MIN_DIST:
                next_p = boarding_queue.pop(0)
                next_p.state = 'walking'
                next_p.pos_m = 0.0
                aisle_passengers.append(next_p)

    end_time = time.time()
    return time_ticks, end_time - start_time

# ==========================================
# 5. 모든 전략 일괄 실행 및 시간 출력
# ==========================================
if __name__ == "__main__":
    strategies = ['RANDOM', 'ZONE', 'WILMA', 'ROW', 'FREE']
    total_seats = NUM_ROWS * SEATS_PER_ROW
    num_passengers = int(total_seats * OCCUPANCY_RATE)
    
    # 실행 시나리오 출력
    print(f"--- 시뮬레이션 시작 (짐 과다 상황: {'ON' if HEAVY_LUGGAGE_SCENARIO else 'OFF'}) ---")
    
    for st in strategies:
        ticks, elapsed = run_simulation(st)
        mins = ticks // 60
        secs = ticks % 60
        print(f"✅ 전략: {st:<8} | ⏱️ 소요 시간: {ticks:>4} Ticks")