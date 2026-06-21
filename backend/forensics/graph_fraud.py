"""
networkx-based Fraud Ring Detection

Builds a graph of applicants, employers, PAN numbers, and properties
across all cases in the database. High-degree shared nodes indicate
fraud rings — multiple fraudulent applications sharing the same fictitious employer,
guarantor, or PAN.
"""
import re

try:
    import networkx as nx
    NX_AVAILABLE = True
except ImportError:
    NX_AVAILABLE = False


def build_fraud_graph(cases_data: list) -> "nx.Graph | None":
    """
    Build a bipartite-style graph from case data.
    
    Nodes:
      - Applicant nodes (type=applicant, id=name)
      - Employer nodes (type=employer, id=employer_name)
      - PAN nodes (type=pan, id=pan_number)
    
    Edges:
      - applicant --[employed_by]--> employer
      - applicant --[has_pan]--> pan
    
    Args:
        cases_data: list of dicts with keys: case_id, applicant_name, employer, pan
    
    Returns:
        networkx.Graph or None if networkx not available
    """
    if not NX_AVAILABLE:
        return None

    G = nx.Graph()

    for case in cases_data:
        case_id = case.get("case_id", "unknown")
        applicant = _normalize(case.get("applicant_name", ""))
        employer = _normalize(case.get("employer", ""))
        pan = (case.get("pan", "") or "").upper().strip()

        if applicant:
            G.add_node(f"APL:{applicant}", type="applicant", case_id=case_id,
                       label=case.get("applicant_name", applicant))

        if employer and employer not in ("unknown", ""):
            G.add_node(f"EMP:{employer}", type="employer",
                       label=case.get("employer", employer))
            if applicant:
                G.add_edge(f"APL:{applicant}", f"EMP:{employer}",
                           relation="employed_by", case_id=case_id)

        if pan and len(pan) == 10 and pan != "UNKNOWN":
            G.add_node(f"PAN:{pan}", type="pan", label=pan)
            if applicant:
                G.add_edge(f"APL:{applicant}", f"PAN:{pan}",
                           relation="has_pan", case_id=case_id)

    return G


def detect_fraud_rings(cases_data: list, current_case_id: str = None) -> dict:
    """
    Detect fraud rings from cases data.
    
    A fraud ring is detected when:
    - An employer node has degree >= 3 (same employer appears in 3+ applications)
    - A PAN node has degree >= 2 (same PAN used by 2+ applicants — impossible)
    - A connected component has 4+ applicant nodes (application cluster)
    
    Args:
        cases_data: list of {case_id, applicant_name, employer, pan}
        current_case_id: if provided, highlights entities linked to this case
    
    Returns:
        {
            fraud_ring_detected: bool,
            ring_size: int,
            suspicious_nodes: [...],
            shared_entities: [...],
            graph_data: {nodes: [...], edges: [...]} for visualization
        }
    """
    if not NX_AVAILABLE or not cases_data:
        return {
            "fraud_ring_detected": False,
            "ring_size": 0,
            "suspicious_nodes": [],
            "shared_entities": [],
            "graph_data": {"nodes": [], "edges": []},
            "note": "networkx not available" if not NX_AVAILABLE else "No case data"
        }

    G = build_fraud_graph(cases_data)
    if G is None:
        return {
            "fraud_ring_detected": False,
            "ring_size": 0,
            "suspicious_nodes": [],
            "shared_entities": [],
            "graph_data": {"nodes": [], "edges": []}
        }

    fraud_detected = False
    ring_size = 0
    suspicious_nodes = []
    shared_entities = []

    # ── Check employer nodes with high degree ──────────────────────────────────
    for node, data in G.nodes(data=True):
        degree = G.degree(node)

        if data.get("type") == "employer" and degree >= 3:
            fraud_detected = True
            connected_applicants = [
                n for n in G.neighbors(node)
                if G.nodes[n].get("type") == "applicant"
            ]
            ring_size = max(ring_size, degree)
            suspicious_nodes.append({
                "node_id": node,
                "type": "employer",
                "label": data.get("label", node),
                "degree": degree,
                "reason": f"Shared employer across {degree} loan applications — possible fictitious employer",
                "connected_applicants": [G.nodes[n].get("label", n) for n in connected_applicants]
            })
            shared_entities.append({
                "entity": data.get("label", node),
                "entity_type": "Employer",
                "appearances": degree,
                "risk": "CRITICAL"
            })

        elif data.get("type") == "employer" and degree == 2:
            connected_applicants = [
                n for n in G.neighbors(node)
                if G.nodes[n].get("type") == "applicant"
            ]
            shared_entities.append({
                "entity": data.get("label", node),
                "entity_type": "Employer",
                "appearances": degree,
                "risk": "MEDIUM",
                "note": "Shared employer in 2 applications — monitor"
            })

        elif data.get("type") == "pan" and degree >= 2:
            # Same PAN used by 2+ different applicants = definite fraud
            fraud_detected = True
            connected = [G.nodes[n].get("label", n) for n in G.neighbors(node)]
            ring_size = max(ring_size, degree + 2)
            suspicious_nodes.append({
                "node_id": node,
                "type": "pan",
                "label": data.get("label", node),
                "degree": degree,
                "reason": f"CRITICAL: PAN {data.get('label')} shared across {degree} applicants — identity theft indicator",
                "connected_applicants": connected
            })
            shared_entities.append({
                "entity": data.get("label", node),
                "entity_type": "PAN Number",
                "appearances": degree,
                "risk": "CRITICAL"
            })

    # ── Large connected components ────────────────────────────────────────────
    for component in nx.connected_components(G):
        applicants_in_component = [
            n for n in component
            if G.nodes[n].get("type") == "applicant"
        ]
        if len(applicants_in_component) >= 4:
            fraud_detected = True
            ring_size = max(ring_size, len(applicants_in_component))

    # ── Build serializable graph for frontend visualization ───────────────────
    graph_nodes = []
    graph_edges = []

    for node, data in G.nodes(data=True):
        node_type = data.get("type", "unknown")
        color_map = {
            "applicant": "#6366f1",
            "employer": "#f59e0b",
            "pan": "#10b981"
        }
        # Highlight suspicious nodes
        is_suspicious = any(s["node_id"] == node for s in suspicious_nodes)
        graph_nodes.append({
            "id": node,
            "label": data.get("label", node)[:20],
            "type": node_type,
            "color": "#ef4444" if is_suspicious else color_map.get(node_type, "#94a3b8"),
            "size": 12 if is_suspicious else 8,
            "suspicious": is_suspicious,
        })

    for u, v, data in G.edges(data=True):
        graph_edges.append({
            "source": u,
            "target": v,
            "relation": data.get("relation", ""),
            "case_id": data.get("case_id", ""),
        })

    return {
        "fraud_ring_detected": fraud_detected,
        "ring_size": ring_size,
        "suspicious_nodes": suspicious_nodes,
        "shared_entities": shared_entities,
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "graph_data": {
            "nodes": graph_nodes,
            "edges": graph_edges
        }
    }


def _normalize(s: str) -> str:
    """Lowercase, strip punctuation for consistent node IDs."""
    if not s:
        return ""
    return re.sub(r'[^a-z0-9\s]', '', s.lower()).strip()
