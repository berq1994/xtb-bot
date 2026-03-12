def poll_status(client, broker_order_id: str):
    return client.get_order_status(broker_order_id)
