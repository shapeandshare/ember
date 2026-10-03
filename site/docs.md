---
layout: doc
title: Documentation
permalink: /docs/
description: "ember documentation: overview, compatibility, responsible use, security, and the agent kit."
---
Guides and references for ember. The same documents live in the
[repository]({{ site.github }}); this section renders them for reading.

<ul class="doc-list">
{%- for doc in site.data.docs %}
  {%- assign durl = '/docs/' | append: doc.slug | append: '/' %}
  <li><a href="{{ durl | relative_url }}">{{ doc.title }}</a></li>
{%- endfor %}
  <li><a href="{{ '/results/' | relative_url }}">Benchmark report</a></li>
</ul>
