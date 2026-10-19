# Copyright 2026 TRUGS LLC
# SPDX-License-Identifier: Apache-2.0

"""Content-identity digest for TRUGs.

A stdlib-only RFC-8785 (JCS) canonical encoding plus a layered, content-addressed
tree digest that yields a self-describing ``tci1-sha256-<hex>`` identifier — the
one shared-spine object both the organizational and the executional security
claims reduce to.

Layers (a consumer pins the one its class needs):

* **L0 — structural_identity**: the node forest (a Merkle fold over ``contains``,
  order-insensitive) plus the sorted, de-duplicated edge-set. Excludes the
  envelope, so it is the cross-version interop floor.
* **L1 — artifact_identity** (the default): ``combine(L0, envelope_digest)`` where
  the envelope digest covers the whole root **minus** ``nodes``/``edges``/the
  ``_derived`` namespace — so future root fields are included *by rule*.
* **L2 — dimension_identity**: the node-leaf projection for one dimension — a
  first-class lens for the organizational class.

Invariants honoured:

* Numbers serialize per RFC-8785 §3.2.2.3 (the ECMAScript ``Number::toString``
  form); no float→decimal migration is required of any committed TRUG.
* The reserved ``_derived`` namespace (any ``_derived`` object key) is excluded
  from the pre-image whole-TRUG, so identity is invariant under recomputation of
  derived/volatile fields (a producer's ``last_refreshed`` never churns identity).
* Pure function of a parsed dict: no file I/O; a content reference is represented
  by its content-address and is **never** resolved (a dangling reference still
  digests).
* The persisted ``.trug.json`` form, the CORE VALID/INVALID verdict, and every
  digest-less graph are left byte-for-byte untouched — this module only reads.

Imports only the standard library (``json`` + ``hashlib``), so it
adds no new runtime dependency to the commons.

<trl>
FUNCTION digest SHALL READ RECORD trug THEN RETURN RECORD content_identity.
</trl>
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

__all__ = [
    "digest",
    "verify",
    "canonical_encoding",
    "content_address",
    "structural_identity",
    "artifact_identity",
    "dimension_identity",
    "envelope_digest",
    "TCI_VERSION",
    "TCI_ALGO",
    "DERIVED_KEY",
]

TCI_VERSION = "tci1"
TCI_ALGO = "sha256"
DERIVED_KEY = "_derived"
#: A content reference marker: ``{"$content_address": "tci1-sha256-<hex>"}``.
#: The digest uses the address literally and never resolves it (purity).
REF_KEY = "$content_address"
#: I-JSON safe-integer domain (RFC 8785 / RFC 7493). Integers outside it are not
#: interoperably representable as JSON numbers and are rejected rather than
#: silently coerced to a lossy double.
_SAFE_INT_MAX = 2 ** 53 - 1


# ── RFC-8785 canonical encoding (JCS) ──────────────────────────────────────────

def _es6_number(f: float) -> str:
    """Serialize a float per RFC-8785 §3.2.2.3 (ECMAScript ``Number::toString``).

    Derives the shortest round-trippable decimal (via ``repr``) then applies the
    ES6 fixed-vs-exponential formatting rules. Matches the ``jcs``/``rfc8785``
    reference libraries byte-for-byte on the finite double domain.
    """
    if f != f or f in (float("inf"), float("-inf")):
        raise ValueError(f"non-finite number is not permitted in canonical encoding: {f!r}")
    if f == 0.0:
        return "0"  # collapses +0.0 and -0.0
    sign = "-" if f < 0 else ""
    r = repr(abs(f))
    if "e" in r:
        mant, _, exp_s = r.partition("e")
        exp = int(exp_s)
    else:
        mant, exp = r, 0
    if "." in mant:
        int_part, frac_part = mant.split(".")
    else:
        int_part, frac_part = mant, ""
    digits = (int_part + frac_part).lstrip("0")
    exp10 = exp - len(frac_part)
    if digits == "":
        return "0"
    stripped = digits.rstrip("0")
    exp10 += len(digits) - len(stripped)
    digits = stripped
    k = len(digits)
    n = exp10 + k
    if k <= n <= 21:
        body = digits + "0" * (n - k)
    elif 0 < n <= 21:
        body = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        body = "0." + "0" * (-n) + digits
    else:
        e = n - 1
        mantissa = digits if k == 1 else digits[0] + "." + digits[1:]
        body = mantissa + "e" + ("+" if e >= 0 else "-") + str(abs(e))
    return sign + body


def _number(v: Any) -> str:
    if isinstance(v, int):  # bool is handled by the caller before this point
        if not (-_SAFE_INT_MAX <= v <= _SAFE_INT_MAX):
            raise ValueError(
                f"integer {v} exceeds the I-JSON safe domain (RFC 8785); "
                "represent it as a string or externalize the value"
            )
        return str(v)
    return _es6_number(v)


def _utf16_key(k: Any) -> bytes:
    if not isinstance(k, str):
        raise TypeError("object keys must be strings for canonical encoding")
    return k.encode("utf-16-be")  # RFC 8785 §3.2.3 sorts by UTF-16 code units


def _encode(v: Any) -> bytes:
    if v is None:
        return b"null"
    if v is True:
        return b"true"
    if v is False:
        return b"false"
    if isinstance(v, str):
        return json.dumps(v, ensure_ascii=False).encode("utf-8")
    if isinstance(v, (int, float)):  # bool already excluded above
        return _number(v).encode("ascii")
    if isinstance(v, (list, tuple)):
        return b"[" + b",".join(_encode(x) for x in v) + b"]"
    if isinstance(v, dict):
        items = sorted(v.items(), key=lambda kv: _utf16_key(kv[0]))
        parts = [
            json.dumps(k, ensure_ascii=False).encode("utf-8") + b":" + _encode(val)
            for k, val in items
        ]
        return b"{" + b",".join(parts) + b"}"
    raise TypeError(f"cannot canonicalize value of type {type(v).__name__}")


def canonical_encoding(obj: Any) -> bytes:
    """Return the RFC-8785 (JCS) canonical UTF-8 encoding of ``obj``.

    Pure RFC-8785 — byte-identical to the ``jcs`` / ``rfc8785`` reference libraries
    on the interoperable JSON domain. The digest pipeline strips the ``_derived``
    namespace *before* calling this, so a digest pre-image never ingests it.
    """
    return _encode(obj)


# ── derived-namespace exclusion + content-address projection ───────────────────

def _strip_derived(obj: Any) -> Any:
    """Recursively drop every ``_derived`` key — the reserved namespace, whole-TRUG."""
    if isinstance(obj, dict):
        return {k: _strip_derived(v) for k, v in obj.items() if k != DERIVED_KEY}
    if isinstance(obj, list):
        return [_strip_derived(x) for x in obj]
    return obj


def _project_content(obj: Any) -> Any:
    """Represent content references by their address; never resolve them.

    A single-key ``{"$content_address": "<tci label>"}`` dict is replaced by a
    stable token carrying just the address. Inline values remain inline, so
    externalizing a value can change the digest. A reference to a missing target
    still digests (no I/O).
    """
    if isinstance(obj, dict):
        if len(obj) == 1 and isinstance(obj.get(REF_KEY), str):
            return {"__content_ref__": obj[REF_KEY]}
        return {k: _project_content(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_project_content(x) for x in obj]
    return obj


def content_address(value: Any) -> str:
    """Content-address of a single value — computed locally, pure, no I/O."""
    return _label(_hash(canonical_encoding(_strip_derived(_project_content(value)))))


# ── the layered digest ─────────────────────────────────────────────────────────

def _hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_obj(obj: Any) -> str:
    return _hash(canonical_encoding(obj))


def _label(hex_digest: str) -> str:
    return f"{TCI_VERSION}-{TCI_ALGO}-{hex_digest}"


def _dimension_of(node: Dict[str, Any]) -> Any:
    dim = node.get("dimension")
    return dim if isinstance(dim, str) else canonical_encoding(dim).decode("utf-8")


def _node_leaf(node: Dict[str, Any]) -> Dict[str, Any]:
    """The CORE fields of a node minus ``contains`` (folded separately) — the leaf."""
    leaf: Dict[str, Any] = {}
    for field in ("id", "type", "parent_id", "metric_level"):
        if field in node:
            leaf[field] = node[field]
    if "dimension" in node:
        leaf["dimension"] = _dimension_of(node)  # B6/B14: dimension is a string
    leaf["properties"] = node.get("properties", {})
    return leaf


def _content_hashes(prepared: Dict[str, Any]) -> List[str]:
    """Every node's content-hash, each folding its ``contains`` subtree order-insensitively."""
    index = {n["id"]: n for n in prepared.get("nodes", []) if isinstance(n, dict) and "id" in n}
    memo: Dict[str, str] = {}

    def content_hash(nid: str, stack: frozenset) -> str:
        if nid in memo:
            return memo[nid]
        if nid in stack:
            raise ValueError(f"cycle detected in the contains-tree at node {nid!r}")
        node = index[nid]
        deeper = stack | {nid}
        child_hashes: List[str] = []
        for cid in dict.fromkeys(node.get("contains", []) or []):  # de-dup, set semantics
            if cid in index:
                child_hashes.append(content_hash(cid, deeper))
            else:
                child_hashes.append(_hash_obj({"unresolved_child": cid}))
        child_hashes.sort()  # FOLD child by content_hash — invariant to contains order
        h = _hash_obj({"leaf": _node_leaf(node), "children": child_hashes})
        memo[nid] = h
        return h

    return sorted(content_hash(nid, frozenset()) for nid in index)


def _edge_set(prepared: Dict[str, Any]) -> List[List[Any]]:
    """The edge-set as sorted, de-duplicated ``[from_id, to_id, relation]`` triples."""
    seen = set()
    out: List[List[Any]] = []
    for e in prepared.get("edges", []) or []:
        if not isinstance(e, dict):
            continue
        frm = e.get("from_id", e.get("from_node"))  # fold legacy aliases (B5)
        to = e.get("to_id", e.get("to_node"))
        rel = e.get("relation")
        key = (frm, to, rel)
        if key in seen:
            continue
        seen.add(key)
        out.append([frm, to, rel])
    out.sort(key=lambda t: (str(t[0]), str(t[1]), str(t[2])))
    return out


def structural_identity(prepared: Dict[str, Any]) -> str:
    """L0 — nodes (Merkle over contains) + the edge-set; excludes the envelope."""
    return _hash_obj({"nodes": _content_hashes(prepared), "edges": _edge_set(prepared)})


def envelope_digest(prepared: Dict[str, Any]) -> str:
    """The digest of the root minus ``nodes``/``edges`` (and, upstream, ``_derived``)."""
    env = {k: v for k, v in prepared.items() if k not in ("nodes", "edges")}
    return _hash_obj(env)


def artifact_identity(prepared: Dict[str, Any]) -> str:
    """L1 — combine(L0, envelope_digest)."""
    return _hash_obj(
        {
            "tci_layer": "L1",
            "structural": structural_identity(prepared),
            "envelope": envelope_digest(prepared),
        }
    )


def dimension_identity(prepared: Dict[str, Any], dimension: str) -> str:
    """L2 — the node-leaf projection for one dimension (a lens)."""
    leaves = sorted(
        _hash_obj(_node_leaf(n))
        for n in prepared.get("nodes", [])
        if isinstance(n, dict) and _dimension_of(n) == dimension
    )
    return _hash_obj({"tci_layer": "L2", "dimension": dimension, "nodes": leaves})


def _prepare(trug: Dict[str, Any]) -> Dict[str, Any]:
    return _strip_derived(_project_content(trug))


def digest(trug: Dict[str, Any], layer: str = "L1", dimension: str | None = None) -> str:
    """Return the ``tci1-sha256-<hex>`` content identity of ``trug`` at ``layer``.

    ``layer`` is ``L0`` (structural), ``L1`` (artifact — the default), or ``L2``
    (a per-dimension lens, which requires ``dimension``).
    """
    prepared = _prepare(trug)
    lyr = layer.upper()
    if lyr == "L0":
        h = structural_identity(prepared)
    elif lyr == "L1":
        h = artifact_identity(prepared)
    elif lyr == "L2":
        if dimension is None:
            raise ValueError("layer L2 (dimension_identity) requires a dimension argument")
        h = dimension_identity(prepared, dimension)
    else:
        raise ValueError(f"unknown layer {layer!r}; expected 'L0', 'L1', or 'L2'")
    return _label(h)


def verify(
    trug: Dict[str, Any],
    declared_identity: str,
    layer: str = "L1",
    dimension: str | None = None,
) -> Dict[str, Any]:
    """Recompute the content identity and compare it to ``declared_identity``.

    Pure comparator — returns ``{"match", "declared", "recomputed", "layer"}``.
    Validator integration is not implemented.
    """
    recomputed = digest(trug, layer=layer, dimension=dimension)
    return {
        "match": recomputed == declared_identity,
        "declared": declared_identity,
        "recomputed": recomputed,
        "layer": layer.upper(),
    }
