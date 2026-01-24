# config.py

# Simulation timing
TICK_DURATION = 0.2  # seconds

# Environment
ENV_HOST = "127.0.0.1"
ENV_PORT = 9000

# Limits
MAX_PREYS = 200
MAX_PREDATORS = 80
MAX_GRASS = 2000

# Initial state
INITIAL_GRASS = 200

# Energy thresholds
H_ENERGY = 30         # hungry/active threshold
R_ENERGY = 60         # reproduction threshold

# Energy dynamics
PREY_INITIAL_ENERGY = 40
PREDATOR_INITIAL_ENERGY = 40

PREY_ENERGY_DECAY = 1
PREDATOR_ENERGY_DECAY = 2

# Food gains
PREY_GRASS_GAIN_PER_UNIT = 1       # 1 grass -> +1 energy
PREDATOR_EAT_GAIN = 30

# Grass dynamics
GRASS_GROWTH_PER_TICK = 5
DROUGHT_GRASS_FACTOR = 0.2         # during drought, growth is reduced

# Decision probabilities
PREY_EAT_PROB = 0.8
PREY_REPRO_PROB = 0.2

PRED_HUNT_PROB = 0.8
PRED_REPRO_PROB = 0.2

# Prey eating request bounds
PREY_MIN_EAT = 1
PREY_MAX_EAT_FACTOR = 2   # requested max = int(R_ENERGY * factor)

# Drought scheduling (env self-timer)
ENABLE_DROUGHT_TIMER = False
DROUGHT_TIMER_EVERY_SEC = 15

DROUGHT_MIN_SECONDS = 8
DROUGHT_MAX_SECONDS = 18
NORMAL_MIN_SECONDS = 10
NORMAL_MAX_SECONDS = 25
