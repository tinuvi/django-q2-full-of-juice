# Brokers

The broker sits between your Django instances and your Django Q2 cluster instances; accepting, saving and delivering task packages.
Currently we support a variety of brokers.

The default Redis broker does not support message receipts.
This means that in case of a catastrophic failure of the cluster server or worker timeouts, tasks that were being executed get lost.
Keep in mind this is not the same as a failing task. If a tasks code crashes, this should only lead to a failed task status.

Even though this might be acceptable in some use cases, you might prefer brokers with message receipts support.
These guarantee delivery by waiting for the cluster to send a receipt after the task has been processed.
In case a receipt has not been received after a set time, the task package is put back in the queue.
Django Q2 supports this behavior by setting the [retry](configure.md#retry) timer on brokers that support message receipts.

Some pointers:

* Don't set the [retry](configure.md#retry) timer to a lower or equal number than the task timeout.
* Retry time includes time the task spends waiting in the clusters internal queue.
* Don't set the [queue_limit](configure.md#queue_limit) so high that tasks time out while waiting to be processed.
* In case a task is worked on twice, the task result will be updated with the latest results.
* In some rare cases a non-atomic broker will re-queue a task after it has been acknowledged.
* If a task runs twice and a previous run has succeeded, the new result will be discarded.
* Limiting the number of retries is handled globally in your actual broker's settings.

Support for more brokers is being worked on.

## Redis

The default broker for Django Q2 clusters.

* Atomic
* Requires [Redis-py](https://github.com/redis/redis-py) client library: `pip install redis`
* Does not need cache framework for monitoring
* Does not support receipts
* Can use existing [django_redis](configure.md#django_redis) connections.
* Configure with [redis_configuration](configure.md#redis_configuration)-py compatible configuration

## IronMQ

This HTTP based queue service is both available directly via [Iron.io](http://www.iron.io/mq/) and as an add-on on Heroku.

* Delivery receipts
* Supports bulk dequeue
* Needs Django's [Cache framework](https://docs.djangoproject.com/en/4.0/topics/cache/#setting-up-the-cache) configured for monitoring
* Requires the [iron-mq](https://github.com/iron-io/iron_mq_python) client library: `pip install iron-mq`
* See the [ironmq_configuration](configure.md#ironmq_configuration) configuration section for options.

## Amazon SQS

Amazon's Simple Queue Service is another HTTP based message queue.
Although [SQS](https://aws.amazon.com/sqs/) is not the fastest, it is stable, cheap and convenient if you already use AWS.

* Delivery receipts
* Maximum message size is 256Kb
* Supports bulk dequeue up to 10 messages with a maximum total size of 256Kb
* Needs Django's [Cache framework](https://docs.djangoproject.com/en/4.0/topics/cache/#setting-up-the-cache) configured for monitoring
* Requires the [boto3](https://github.com/boto/boto3) client library: `pip install boto3`
* See the [sqs_configuration](configure.md#sqs_configuration) configuration section for options.

## MongoDB

This highly scalable NoSQL database makes for a very fast and reliably persistent at-least-once message broker.
Usually available on most PaaS providers, as [open-source](https://www.mongodb.org/) or commercial [enterprise](https://www.mongodb.com/lp/download/mongodb-enterprise) edition.

* Delivery receipts
* Needs Django's [Cache framework](https://docs.djangoproject.com/en/4.0/topics/cache/#setting-up-the-cache) configured for monitoring
* Can be configured as the Django cache-backend through several open-source cache providers.
* Requires the [pymongo](https://github.com/mongodb/mongo-python-driver) driver: `pip install pymongo`
* See the [mongo_configuration](configure.md#mongo_configuration) configuration section for options.

<a id="orm_broker"></a>
## Django ORM

Select this to use Django's database backend as a message broker.
Unless you have configured a dedicated database backend for it, this should probably not be your first choice for a high traffic setup.
However for a medium message rate and scheduled tasks, this is the most convenient guaranteed delivery broker.

* Delivery receipts
* Supports bulk dequeue
* Needs Django's [Cache framework](https://docs.djangoproject.com/en/4.0/topics/cache/#setting-up-the-cache) configured for monitoring
* Can be [configured](https://docs.djangoproject.com/en/4.0/topics/cache/#database-caching) as its own cache backend.
* Queue editable in Django Admin
* See the [orm_configuration](configure.md#orm_configuration) configuration on how to set it up.

## Custom Broker

You can override the `Broker` or any of its existing derived broker types.

```python
# example Custom broker.py
from django_q.brokers import Broker

class CustomBroker(Broker):
    def info(self):
        return 'My Custom Broker'
```

Using the [broker_class](configure.md#broker_class) configuration setting you can then instruct Django Q2 to use this instead of one of the existing brokers:

```python
# example Custom broker class connection

Q_CLUSTER = {
    'name': 'Custom',
    'workers': 8,
    'timeout': 60,
    'broker_class: 'myapp.broker.CustomBroker'
}
```

If you do write a custom broker for one of the many message queueing servers out there we don't support yet, please consider contributing it to the project.

## Reference

The `Broker` class is used internally to communicate with the different types of brokers.
You can override this class if you want to contribute and support your own broker.

### Broker

**Methods**

| Method | Description |
|---|---|
| `enqueue(task)` | Sends a task package to the broker queue and returns a tracking id if available. |
| `dequeue()` | Gets packages from the broker and returns a list of tuples with a tracking id and the package. |
| `acknowledge(id)` | Notifies the broker that the task has been processed. Only works with brokers that support delivery receipts. |
| `fail(id)` | Tells the broker that the message failed to be processed by the cluster. Only available on brokers that support this. Currently only occurs when a cluster fails to unpack a task package. |
| `delete(id)` | Instructs the broker to delete this message from the queue. |
| `purge_queue()` | Empties the current queue of all messages. |
| `delete_queue()` | Deletes the current queue from the broker. |
| `queue_size()` | Returns the amount of messages in the brokers queue. |
| `lock_size()` | Optional method that returns the number of messages currently awaiting acknowledgement. Only implemented on brokers that support it. |
| `ping()` | Returns True if the broker can be reached. |
| `info()` | Shows the name and version of the currently configured broker. |

### brokers.get_broker()

```python
brokers.get_broker()
```

Returns a `Broker` instance based on the current configuration.
