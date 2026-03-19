{% for section, _ in sections.items() %}
{% set underline = "#" %}
{% if sections[section] %}

### {{ versiondata.version }} {{ section }}

{% for category, val in sections[section].items() %}
#### {{ category }}

{% for text, values in val.items() %}
- {{ text }}
{% endfor %}
{% endfor %}
{% else %}
No significant changes.
{% endif %}
{% endfor %}
