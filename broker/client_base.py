class BrokerClientBase:
    def submit_order(self, order: dict):
        raise NotImplementedError

    def get_order_status(self, broker_order_id: str):
        raise NotImplementedError

    def cancel_order(self, broker_order_id: str):
        raise NotImplementedError
