# Installation

- Install the latest version with pip:

    ```bash
    pip install django-q2-full-of-juice
    ```

- Add `django_q` to `INSTALLED_APPS` in your project's `settings.py`:

    ```python
    INSTALLED_APPS = (
        # other apps
        'django_q',
    )
    ```

- Run Django migrations to create the database tables:

    ```bash
    python manage.py migrate
    ```

- Choose a message [broker](brokers.md), configure it and install the appropriate client library.

- Run the Django Q2 cluster in order to handle tasks asynchronously:

    ```bash
    python manage.py qcluster
    ```

## Migrate from Django-Q to Django-Q2

If you have an application with django-q running right now, you can simply swap the libraries and you should be good to go.

```bash
pip uninstall django-q  # you might have to uninstall django-q add-ons as well
pip install django-q2-full-of-juice
```

Then migrate the database to get the latest tables/fields:

```bash
python manage.py migrate
```

## Requirements

Django Q2 is tested for Python 3.12 and 3.13.

- [Django](https://www.djangoproject.com)

    Django Q2 aims to use as much of Django's standard offerings as possible. The code is tested against Django versions `5.0.x` and `6.0.x`.

- [Django-picklefield](https://github.com/gintas/django-picklefield)

    Used to store args, kwargs and result objects in the database.

### Optional

- [Blessed](https://github.com/jquast/blessed) is used to display the statistics in the terminal:

    ```bash
    pip install blessed
    ```

- [Redis-py](https://github.com/redis/redis-py) client maintained by the Redis team is used to interface with Redis:

    ```bash
    pip install redis
    ```

- <a id="psutil_package"></a>[Psutil](https://github.com/giampaolo/psutil) is an optional requirement and adds CPU affinity settings to the cluster:

    ```bash
    pip install psutil
    ```

- [setproctitle](https://github.com/dvarrazzo/py-setproctitle) is an optional requirement used to set informative process titles:

    ```bash
    pip install setproctitle
    ```

- [Hiredis](https://github.com/redis/hiredis) parser. This C library maintained by the core Redis team is faster than the standard PythonParser during high loads:

    ```bash
    pip install hiredis
    ```

- [Boto3](https://github.com/boto/boto3) is used for the Amazon SQS broker:

    ```bash
    pip install boto3
    ```

- [Iron-mq](https://github.com/iron-io/iron_mq_python) is the official python binding for the IronMQ broker:

    ```bash
    pip install iron-mq
    ```

- [Pymongo](https://github.com/mongodb/mongo-python-driver) is needed if you want to use MongoDB as a message broker:

    ```bash
    pip install pymongo
    ```

- [Redis](http://redis.io/) server is the default broker for Django Q2. It provides the best performance and does not require Django's cache framework for monitoring.

- [MongoDB](https://www.mongodb.org/) is a highly scalable NoSQL database which makes for a very fast and reliably persistent at-least-once message broker. Usually available on most PaaS providers.

- [Pyrollbar](https://github.com/rollbar/pyrollbar) is an error notifier for [Rollbar](https://rollbar.com/) which lets you manage your worker errors in one place. Needs a Rollbar account and access key. It is wired into Django Q2 through the `django-q-rollbar` add-on (see [Add-ons](#add-ons)):

    ```bash
    pip install django-q2-full-of-juice[rollbar]
    ```

- <a id="croniter_package"></a>[Croniter](https://github.com/kiorky/croniter) is an optional package that is used to parse cron expressions for the scheduler:

    ```bash
    pip install croniter
    ```

## Add-ons

- [django-q-rollbar](https://github.com/danielwelch/django-q-rollbar) is a Rollbar error reporter:

    ```bash
    pip install django-q2-full-of-juice[rollbar]
    ```

- [django-q-sentry](https://github.com/danielwelch/django-q-sentry) is a Sentry error reporter:

    ```bash
    pip install django-q2-full-of-juice[sentry]
    ```

- [django-q-email](https://github.com/joeyespo/django-q-email) is a compatible Django email backend that will automatically async queue your emails.

## OS X

Running Django Q2 on OS X should work fine, except for the following known issues:

- `multiprocessing.Queue.qsize()` is not supported. This leads to the monitor not reporting the internal queue size of clusters running under OS X.
- CPU count through `multiprocessing.cpu_count()` does not work. Installing [psutil](#psutil_package) provides Django Q2 with an alternative way of determining the number of CPUs on your system.
- CPU affinity is provided by [psutil](#psutil_package) which at this time does not support this feature on OS X. The code however is aware of this and will fake the CPU affinity assignment in the logs without actually assigning it. This way you can still develop with this setting.

## Windows

The cluster and worker multiprocessing code depend on the OS's ability to fork; unfortunately forking is not supported under Windows.
You should however be able to develop and test without the cluster by setting the `sync` option to `True` in the configuration.
This will run all `async` calls inline through a single cluster worker without the need for forking.
Other known issues are:

- `os.getppid()` is only supported under Windows since Python 3.2. If you use an older version you need to install [psutil](#psutil_package) as an alternative.
- CPU count through `multiprocessing.cpu_count()` occasionally fails on servers. Installing [psutil](#psutil_package) provides Django Q2 with an alternative way of determining the number of CPUs on your system.
- The monitor and info commands rely on the Curses package which is not officially supported on Windows.

## Python

Current tests are performed with 3.12 and 3.13.
If you do encounter any regressions with earlier versions, please submit an issue on [github](https://github.com/tinuvi/django-q2-full-of-juice).

### Open-source packages

Django Q2 is always tested with the latest versions of the required and optional Python packages. We try to keep the dependencies as up to date as possible.
You can reference the [pyproject.toml](https://github.com/tinuvi/django-q2-full-of-juice/blob/master/pyproject.toml) file to determine which versions are currently being used for tests and development.

### Django

We strive to be compatible with the most recent Django releases.
At the moment this means we support the 5.0.x and 6.0.x releases.

Since Django Q2 requires Python >= 3.12, we cannot support older Django releases that do not run on it.
For this you can always use older releases, but they are no longer maintained.
