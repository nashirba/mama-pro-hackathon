# Django ships no NUMBER_GROUPING for kk, so floatformat:"0g" printed prices ungrouped.
DECIMAL_SEPARATOR = ","
THOUSAND_SEPARATOR = "\xa0"
NUMBER_GROUPING = 3
