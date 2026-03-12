from broker.client_base import BrokerClientBase

class PaperBrokerClient(BrokerClientBase):
    def submit_order(self, order: dict):
        return {
            "submitted": True,
            "broker_order_id": f"paper-{order.get('symbol', 'UNK')}-001",
            "mode": "paper",
        }

    def get_order_status(self, broker_order_id: str):
        return {
            "broker_order_id": broker_order_id,
            "status": "FILLED",
            "mode": "paper",
        }

    def cancel_order(self, broker_order_id: str):
        return {
            "broker_order_id": broker_order_id,
            "cancelled": True,
            "mode": "paper",
        }
