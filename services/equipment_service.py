import logging
from auth.security import generate_uuid
from database.connection import query_one, query_all, execute_statement

logger = logging.getLogger(__name__)

STANDARD_CATEGORIES = [
    "Cardio", "Chest", "Back", "Legs", "Shoulders", "Arms", "Core", "Free Weights"
]

DEFAULT_EQUIPMENT = [
    {
        "name": "Commercial Treadmill Pro",
        "category": "Cardio",
        "target_muscle": "Cardiovascular, Legs & Endurance",
        "quantity": 4,
        "status": "operational",
        "description": "High-performance motorized running deck with multi-incline and heart rate monitoring.",
        "instructions": "Clip safety key, select speed, and maintain posture. Great for 10-15m warmups or HIIT."
    },
    {
        "name": "Olympic 3D Smith Machine",
        "category": "Chest",
        "target_muscle": "Chest, Shoulders & Quads",
        "quantity": 2,
        "status": "operational",
        "description": "Guided vertical bar path with safety lockouts for squats, bench presses, and shoulder presses.",
        "instructions": "Adjust safety catches to shoulder height. Rotate bar slightly forward to unrack."
    },
    {
        "name": "Dual Adjustable Cable Crossover",
        "category": "Chest",
        "target_muscle": "Chest, Biceps & Triceps",
        "quantity": 2,
        "status": "operational",
        "description": "Multi-angle dual pulley station with multi-grip pull-up bar.",
        "instructions": "Set pulleys to desired height for cable flyes, tricep pushdowns, or face pulls."
    },
    {
        "name": "45-Degree Leg Press Machine",
        "category": "Legs",
        "target_muscle": "Quadriceps, Glutes & Hamstrings",
        "quantity": 2,
        "status": "operational",
        "description": "Heavy-duty plate-loaded 45-degree angled sled with dual safety lockout levers.",
        "instructions": "Place feet shoulder-width apart on platform. Lower sled until knees reach 90 degrees."
    },
    {
        "name": "Lat Pulldown & Low Row Station",
        "category": "Back",
        "target_muscle": "Latissimus Dorsi, Rhomboids & Biceps",
        "quantity": 2,
        "status": "operational",
        "description": "Smooth selectorized cable station with thigh-pad stabilization and neutral grip bar.",
        "instructions": "Lock thighs under pads, grip bar wide, pull down toward upper chest while squeezing back."
    },
    {
        "name": "Heavy Urethane Dumbbell Rack (2.5kg - 40kg)",
        "category": "Free Weights",
        "target_muscle": "Full Body Compound & Isolation",
        "quantity": 1,
        "status": "operational",
        "description": "Complete twin-tier dumbbell set with commercial rubberized urethane heads.",
        "instructions": "Always return dumbbells to their designated tier slot after completing sets."
    },
    {
        "name": "Pec Fly / Rear Delt Fly Machine",
        "category": "Shoulders",
        "target_muscle": "Pectorals & Posterior Deltoids",
        "quantity": 2,
        "status": "operational",
        "description": "Dual-function selectorized machine with adjustable arm levers and seat height.",
        "instructions": "Face inward for rear delt flies, face outward for chest pec dec flyes."
    },
    {
        "name": "Olympic Power Squat Rack",
        "category": "Legs",
        "target_muscle": "Quads, Glutes & Spinal Erectors",
        "quantity": 2,
        "status": "operational",
        "description": "Heavy steel upright cage with adjustable J-hooks and commercial safety spotter arms.",
        "instructions": "Set J-hooks at mid-chest height. Always use collar clamps on barbell sleeves."
    },
    {
        "name": "Seated Preacher Arm Curl Bench",
        "category": "Arms",
        "target_muscle": "Biceps Brachii",
        "quantity": 2,
        "status": "operational",
        "description": "Ergonomically angled arm pad bench paired with EZ-curl barbell.",
        "instructions": "Rest armpits snugly on top of pad. Curl barbell upward without lifting elbows."
    },
    {
        "name": "Seated Abdominal Crunch Machine",
        "category": "Core",
        "target_muscle": "Rectus Abdominis & Obliques",
        "quantity": 1,
        "status": "operational",
        "description": "Biomechanical seated crunch station with selectorized pin weight stack.",
        "instructions": "Hold overhead handles, flex core downward while contracting abdominal muscles."
    }
]

def seed_default_equipment_if_empty():
    """Ensure standard machines are seeded so gym facilities tab is populated."""
    try:
        count = query_one("SELECT COUNT(*) AS total FROM equipment;")
        if count and count["total"] == 0:
            for eq in DEFAULT_EQUIPMENT:
                create_equipment(
                    name=eq["name"],
                    category=eq["category"],
                    target_muscle=eq["target_muscle"],
                    quantity=eq["quantity"],
                    status=eq["status"],
                    description=eq["description"],
                    instructions=eq["instructions"]
                )
            logger.info("Seeded default gym equipment directory.")
    except Exception as e:
        logger.debug("Equipment check: %s", e)

def get_all_equipment(category=None, status=None):
    """Retrieve all equipment with optional category/status filters."""
    seed_default_equipment_if_empty()
    where = ["1=1"]
    params = []
    if category and category != "all":
        where.append("category = %s")
        params.append(category)
    if status and status != "all":
        where.append("status = %s")
        params.append(status)

    sql = f"SELECT * FROM equipment WHERE {' AND '.join(where)} ORDER BY category ASC, name ASC;"
    return query_all(sql, tuple(params))

def get_equipment_by_id(equipment_id):
    """Retrieve single equipment item by ID."""
    return query_one("SELECT * FROM equipment WHERE id = %s;", (equipment_id,))

def create_equipment(name, category, target_muscle=None, quantity=1, status="operational", description=None, instructions=None):
    """Add a new machine or equipment to the gym facilities."""
    eq_id = generate_uuid()
    sql = """
        INSERT INTO equipment (id, name, category, target_muscle, quantity, status, description, instructions)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
    """
    execute_statement(sql, (
        eq_id, name.strip(), category.strip(),
        (target_muscle or "").strip() or None,
        int(quantity or 1), status.strip(),
        (description or "").strip() or None,
        (instructions or "").strip() or None
    ))
    return get_equipment_by_id(eq_id)

def update_equipment(equipment_id, name, category, target_muscle=None, quantity=1, status="operational", description=None, instructions=None):
    """Update details of an existing gym equipment."""
    sql = """
        UPDATE equipment
        SET name = %s, category = %s, target_muscle = %s, quantity = %s, status = %s,
            description = %s, instructions = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s;
    """
    execute_statement(sql, (
        name.strip(), category.strip(),
        (target_muscle or "").strip() or None,
        int(quantity or 1), status.strip(),
        (description or "").strip() or None,
        (instructions or "").strip() or None,
        equipment_id
    ))
    return get_equipment_by_id(equipment_id)

def delete_equipment(equipment_id):
    """Remove equipment from gym directory."""
    eq = get_equipment_by_id(equipment_id)
    if not eq:
        raise ValueError("Equipment not found.")
    execute_statement("DELETE FROM equipment WHERE id = %s;", (equipment_id,))
    return True
