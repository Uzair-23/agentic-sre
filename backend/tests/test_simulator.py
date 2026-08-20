from simulator.incident_generator import IncidentGenerator

def test_incident_generation():
    gen = IncidentGenerator()
    
    # Test memory leak
    mem_logs = gen.get_incident("memory_leak")
    assert any("OOMKilled" in msg for _, _, msg in mem_logs)
    
    # Test bad deploy
    deploy_logs = gen.get_incident("bad_deploy")
    assert any("deploy event" in msg for _, _, msg in deploy_logs)
    assert any("ERROR 500" in msg for _, _, msg in deploy_logs)