from datetime import datetime, timedelta
import random
from typing import List, Tuple

LogEntry = Tuple[str, str, str]

class IncidentGenerator:
    """Generates deterministic synthetic log streams for agent evals."""
    
    def __init__(self, start_time: datetime = None):
        self.base_time = start_time or (datetime.now() - timedelta(hours=1))
    
    def _generate_noise(self, service: str, minutes: int = 10) -> List[LogEntry]:
        return [
            ((self.base_time + timedelta(minutes=i)).isoformat(), service, f"Health check OK. CPU {random.randint(10, 30)}%")
            for i in range(minutes)
        ]

    def get_incident(self, incident_type: str) -> List[LogEntry]:
        if incident_type == "memory_leak":
            logs = self._generate_noise("payment-service", 5)
            for i in range(1, 6):
                logs.append(((self.base_time + timedelta(minutes=5+i)).isoformat(), "payment-service", f"memory usage {60 + (i * 7)}%"))
            logs.append(((self.base_time + timedelta(minutes=11)).isoformat(), "payment-service", "OOMKilled, restarting"))
            return sorted(logs, key=lambda x: x[0])
            
        elif incident_type == "bad_deploy":
            logs = self._generate_noise("auth-service", 5)
            deploy_ts = self.base_time + timedelta(minutes=5)
            logs.append((deploy_ts.isoformat(), "auth-service", "deploy event — v2.3.1 rolled out"))
            for i in range(1, 5):
                logs.append(((deploy_ts + timedelta(minutes=i)).isoformat(), "auth-service", "ERROR 500: Invalid token signature check failed"))
            return sorted(logs, key=lambda x: x[0])
            
        elif incident_type == "dependency_timeout":
            logs = self._generate_noise("cart-service", 5)
            for i in range(5, 10):
                logs.append(((self.base_time + timedelta(minutes=i)).isoformat(), "cart-service", "CRITICAL: Timeout waiting for inventory-db"))
            return sorted(logs, key=lambda x: x[0])
            
        raise ValueError(f"Unknown incident type: {incident_type}")