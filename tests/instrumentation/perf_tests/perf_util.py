import elasticapm


@elasticapm.capture_span()
def go_someplace_else():
    with elasticapm.capture_span('at-someplace-else'):
        pass
