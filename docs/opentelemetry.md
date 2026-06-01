# OpenTelemetry

Need distributed tracing that survives the queue boundary? The companion package [`opentelemetry-instrumentation-django-q2-full-of-juice`](https://github.com/tinuvi/opentelemetry-instrumentation-django-q2-full-of-juice) turns the [lifecycle signals](signals.md) this fork ships into real OpenTelemetry spans. An `HTTP request → task A → task B → task C` graph then shows up as **one continuous distributed trace**.

It propagates trace context (and W3C Baggage) producer → broker → worker — the carrier rides inside the signed task payload — and emits producer/consumer spans, duration histograms, and messaging semantic-convention attributes. The chain-progress signals (`pre_chain_progress` / `post_chain_progress`) are unique to this fork: they let every link of an `async_chain` land on the same trace.

## Install

Install it alongside django-q2:

```bash
pip install opentelemetry-instrumentation-django-q2-full-of-juice
```

## Enable

Turn it on once, before any worker forks (your `AppConfig.ready()` is the canonical spot):

```python
from opentelemetry_instrumentation_django_q2 import DjangoQ2Instrumentor

DjangoQ2Instrumentor().instrument()
```

Or activate it with zero code via the OpenTelemetry bootstrap CLI:

```bash
opentelemetry-instrument python manage.py qcluster
```

!!! tip
    See the [package documentation](https://github.com/tinuvi/opentelemetry-instrumentation-django-q2-full-of-juice) for the full capability matrix, bring-your-own-provider setup, and caveats.
