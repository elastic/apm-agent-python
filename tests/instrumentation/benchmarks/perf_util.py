import elasticapm

capture_span = elasticapm.capture_span if hasattr(elasticapm, 'capture_span') else elasticapm.trace


@capture_span()
def go_someplace_else():
    with capture_span('at-someplace-else'):
        pass
