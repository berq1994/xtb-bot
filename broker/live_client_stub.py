from broker.client_base import BrokerClientBase

class LiveBrokerClientStub(BrokerClientBase):
    def submit_order(self, order: dict):
        return {
            "submitted": False,
            "broker_order_id": None,
            "mode": "live_stub_locked",
            "reason": "REAL_BROKER_NOT_CONNECTED",
        }

    def get_order_status(self, broker_order_id: str):
        return {
            "broker_order_id": broker_order_id,
            "status": "UNKNOWN",
            "mode": "live_stub_locked",
        }

    def cancel_order(self, broker_order_id: str):
        return {
            "broker_order_id": broker_order_id,
            "cancelled": False,
            "mode": "live_stub_locked",
        }
