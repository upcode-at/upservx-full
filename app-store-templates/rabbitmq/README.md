# RabbitMQ

RabbitMQ is a widely deployed open-source message broker. It enables applications to communicate asynchronously by sending and receiving messages via queues, supporting AMQP, MQTT, and STOMP protocols.

## Ports

| Port | Purpose |
|---|---|
| 5672 | AMQP protocol – used by producers and consumers |
| 15672 | Management UI (HTTP) |

## Before You Start

**Change the default credentials** in `docker-compose.yml`:

```yaml
- RABBITMQ_DEFAULT_USER=admin
- RABBITMQ_DEFAULT_PASS=changeme_strong_password
```

Generate a strong password:
```bash
openssl rand -base64 20
```

## Accessing the Management UI

Open your browser and navigate to:

```
http://<your-server-ip>:15672
```

Log in with the credentials set in `RABBITMQ_DEFAULT_USER` and `RABBITMQ_DEFAULT_PASS`.

The management UI lets you:
- Create and monitor queues, exchanges, and bindings
- Publish and consume messages manually
- Manage users and virtual hosts
- View live throughput and connection stats

## Connecting Producers & Consumers

Use the AMQP URL format:

```
amqp://admin:changeme_strong_password@<your-server-ip>:5672/
```

Example (Python with pika):
```python
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host="localhost",
        credentials=pika.PlainCredentials("admin", "changeme_strong_password")
    )
)
channel = connection.channel()
channel.queue_declare(queue="hello")
channel.basic_publish(exchange="", routing_key="hello", body="Hello World!")
connection.close()
```

## Additional Protocols

Enable extra protocol plugins via the management UI or by running:

```bash
# MQTT (port 1883)
docker exec rabbitmq rabbitmq-plugins enable rabbitmq_mqtt

# STOMP (port 61613)
docker exec rabbitmq rabbitmq-plugins enable rabbitmq_stomp

# AMQP 1.0
docker exec rabbitmq rabbitmq-plugins enable rabbitmq_amqp1_0
```

## Virtual Hosts

Virtual hosts (vhosts) isolate groups of queues and exchanges. Create additional vhosts in the management UI under **Admin → Virtual Hosts**.

## More Information

- [RabbitMQ Website](https://www.rabbitmq.com)
- [GitHub](https://github.com/rabbitmq/rabbitmq-server)
- [Docker Hub](https://hub.docker.com/_/rabbitmq)
- [Documentation](https://www.rabbitmq.com/docs)
- [Tutorials](https://www.rabbitmq.com/tutorials)
