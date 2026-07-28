"use strict";

const upstream = require("brace-expansion-v5");
const expand = upstream.expand;

module.exports = Object.assign(expand, upstream);
