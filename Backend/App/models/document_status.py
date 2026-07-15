PHASES = [
    "phase_0_ingestion",
    "phase_1_beat_extraction",
    "phase_2_entity_census",
    "phase_3_span_classification",
    "phase_4_character_synthesis",
    "phase_5_lore_synthesis",
    "phase_6_entity_beat_linking",
    "phase_7_graph_construction",
    "phase_8_world_state_init",
]

def default_status():
    return {phase: "pending" for phase in PHASES}  # pending | in_progress | done |

def update_phase_status(session, doc, phase: str, state: str):
    if phase not in PHASES:
        raise ValueError(f"Unknown phase: {phase}")
    status = dict(doc.status)
    status[phase] = state
    doc.status = status
    session.commit()