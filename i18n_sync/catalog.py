"""Reading and writing Xcode String Catalogs (.xcstrings)."""

import json
import re
from pathlib import Path

QUANTITIES = ["zero", "one", "two", "few", "many", "other"]
# Each pattern matches an escaped "%%" first, so "%% de" is a percent sign and the
# words after it, not a "% d" specifier; callers skip those matches.
PLURAL_VARIABLE = re.compile(r"%%|%(?:(\d+)\$)?#@(\w+)@")
COUNT_ARGUMENT = re.compile(r"%%|%arg")
FORMAT_SPECIFIER = re.compile(
    r"%%|%(?:\d+\$)?[-+ 0#]*\d*(?:\.\d+)?(?:ll|l|hh|h|q|z|t|j)?[@dDiuUxXoOfFeEgGcCsSpaA]"
)
INTEGER_SPECIFIER = re.compile(r"%%|%(\d+\$)?([-+ 0#]*\d*)(?:ll|l)?([diu])")
# Xcode refuses a plain plural whose forms leave the number out ("балл", "балла"), so
# such a plural goes through a substitution that names the number once.
BARE_PLURAL = "%#@count@"


class Catalog:
    """One .xcstrings file: plain strings and plurals, per key and language.

    Plurals use the YAML shape of the rest of the tool: {quantity: value}, with
    `_format_key` when the plural sits inside a longer sentence. A localization the
    YAML cannot express, such as a variation by device or several substitutions in one
    string, is not read and is written back exactly as it was.
    """

    def __init__(self, path: Path):
        self.path = path
        self.removed_languages: set[str] = set()
        self.data = {"sourceLanguage": "en", "strings": {}, "version": "1.0"}
        if path.exists():
            self.data = json.loads(path.read_text(encoding="utf-8"))

    @property
    def source_language(self) -> str:
        return self.data.get("sourceLanguage", "en")

    def read(self) -> tuple[dict, dict]:
        """Return ({key: {lang: value}}, {key: {lang: {quantity: value}}})."""
        strings, plurals = {}, {}
        for key, entry in self.data.get("strings", {}).items():
            for lang, localization in entry.get("localizations", {}).items():
                kind = self._kind(localization)
                if kind == "plural":
                    plurals.setdefault(key, {})[lang] = self._plural_forms(localization)
                elif kind == "string":
                    strings.setdefault(key, {})[lang] = localization["stringUnit"].get(
                        "value", ""
                    )
        return strings, plurals

    def write(self, strings: dict, plurals: dict, kept_languages: set[str]) -> int:
        """Replace the localizations the YAML holds, keeping everything else.

        Per-key fields such as comments stay, and so does any localization the YAML
        cannot express, unless its language had strings the YAML expresses and is in
        none of `kept_languages`, the YAML's languages: that language was removed.
        The source language is never removed. A key the YAML no longer has is
        removed unless such a localization keeps it. Every written value is marked
        `translated`: the YAML is the source, so a `needs_review` or `new` state
        Xcode set is overwritten.

        Returns how many translations were missing; a missing one is left out, so the
        app falls back to the source language instead of showing an empty string.
        """
        old = self.data.get("strings", {})
        languages = {lang for values in strings.values() for lang in values}
        languages |= {
            lang
            for values in plurals.values()
            for lang in values
            if lang != "_format_key"
        }
        removed = (
            {
                lang
                for entry in old.values()
                for lang, localization in entry.get("localizations", {}).items()
                if self._kind(localization) is not None
            }
            - languages
            - kept_languages
            - {self.source_language}
        )
        self.removed_languages = removed
        kept = {
            key: {
                lang: localization
                for lang, localization in entry.get("localizations", {}).items()
                if self._kind(localization) is None and lang not in removed
            }
            for key, entry in old.items()
        }
        kept = {
            key: localizations for key, localizations in kept.items() if localizations
        }
        missing = 0
        entries = {}
        for key in sorted(set(strings) | set(plurals) | set(kept)):
            entry = {k: v for k, v in old.get(key, {}).items() if k != "localizations"}
            entry.setdefault("extractionState", "manual")
            localizations = dict(kept.get(key, {}))
            in_yaml = key in strings or key in plurals
            for lang in sorted(languages):
                if lang in localizations:
                    continue
                if key in plurals and lang in plurals[key]:
                    localizations[lang] = self._plural_localization(plurals[key], lang)
                elif (strings.get(key, {}).get(lang) or "").strip():
                    localizations[lang] = self._unit(strings[key][lang])
                elif in_yaml:
                    missing += 1
                    print(f"Warning: Missing '{key}' for language '{lang}'")
            entry["localizations"] = dict(sorted(localizations.items()))
            entries[key] = entry
        self.data["strings"] = entries
        self.data.setdefault("version", "1.0")
        self.path.write_text(
            json.dumps(
                self.data,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
                separators=(",", " : "),
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"Updated {self.path}")
        return missing

    def _kind(self, localization: dict) -> str | None:
        """'string' or 'plural' when the YAML can hold it, otherwise None."""
        variations = localization.get("variations", {})
        substitutions = localization.get("substitutions", {})
        if set(variations) == {"plural"} and not substitutions:
            return "plural"
        if variations:
            return None
        if "stringUnit" not in localization:
            return None
        if not substitutions:
            return "string"
        if len(substitutions) == 1:
            (substitution,) = substitutions.values()
            if set(substitution.get("variations", {})) == {"plural"}:
                return "plural"
        return None

    def _unit(self, value: str) -> dict:
        return {"stringUnit": {"state": "translated", "value": value}}

    def _variations(self, forms: dict) -> dict:
        return {
            "plural": {
                quantity: self._unit(forms[quantity])
                for quantity in QUANTITIES
                if quantity in forms
            }
        }

    def _plural_localization(self, key_plurals: dict, lang: str) -> dict:
        forms = {k: v for k, v in key_plurals[lang].items() if k != "_format_key"}
        format_key = key_plurals[lang].get("_format_key") or key_plurals.get(
            "_format_key"
        )
        if not format_key:
            if all(_specifiers(INTEGER_SPECIFIER, value) for value in forms.values()):
                return {"variations": self._variations(forms)}
            format_key = BARE_PLURAL
        match = _first(PLURAL_VARIABLE, format_key)
        if match is None:
            raise ValueError(f"No %#@name@ placeholder in plural format {format_key!r}")
        argument = (
            int(match.group(1) or 0)
            or len(_specifiers(FORMAT_SPECIFIER, format_key[: match.start()])) + 1
        )
        substitution = {
            "argNum": argument,
            "formatSpecifier": "lld",
            "variations": self._variations(
                {
                    quantity: self._name_the_count(value)
                    for quantity, value in forms.items()
                }
            ),
        }
        return {
            **self._unit(format_key),
            "substitutions": {match.group(2): substitution},
        }

    def _name_the_count(self, value: str) -> str:
        """Write the plural's own number as %arg; any other number stays as it is."""
        return _replace_first(INTEGER_SPECIFIER, value, "%arg")

    def _plural_forms(self, localization: dict) -> dict:
        plural = localization.get("variations", {}).get("plural")
        if plural is not None:
            return {
                quantity: plural[quantity]["stringUnit"]["value"]
                for quantity in QUANTITIES
                if quantity in plural
            }
        (substitution,) = localization["substitutions"].values()
        plural = substitution["variations"]["plural"]
        forms = {
            quantity: _replace_first(
                COUNT_ARGUMENT, plural[quantity]["stringUnit"]["value"], "%lld"
            )
            for quantity in QUANTITIES
            if quantity in plural
        }
        if localization["stringUnit"]["value"] != BARE_PLURAL:
            forms["_format_key"] = localization["stringUnit"]["value"]
        return forms


def widen_integer_specifiers(value: str) -> str:
    """Turn %d, %i and %u, with their flags, into the long forms Xcode's symbols take as Int.

    `%02d` becomes `%02lld`, `%u` becomes `%llu`; a value already long is left alone.
    """

    def widen(match: re.Match) -> str:
        if match.group(0) == "%%":
            return "%%"
        conversion = "d" if match.group(3) == "i" else match.group(3)
        return f"%{match.group(1) or ''}{match.group(2)}ll{conversion}"

    return INTEGER_SPECIFIER.sub(widen, value)


def plural_variable(format_key: str) -> str | None:
    """The name in the first %#@name@ or %N$#@name@ that is not escaped as %%#@."""
    match = _first(PLURAL_VARIABLE, format_key)
    return match.group(2) if match else None


def plural_variables(format_key: str) -> list[str]:
    """Every name a format key substitutes, escaped %%#@ left out."""
    return [
        m.group(2) for m in PLURAL_VARIABLE.finditer(format_key) if m.group(0) != "%%"
    ]


def fill_plural_variable(format_key: str, form: str) -> str:
    """Put a plural form where the format key's own %#@name@ stands.

    A numbered placeholder hands its number to the form's count, so
    "%1$@ has %2$#@count@" with "%lld files" gives "%1$@ has %2$lld files".
    """
    match = _first(PLURAL_VARIABLE, format_key)
    if match is None:
        return format_key
    count = _first(INTEGER_SPECIFIER, form)
    if match.group(1) and count is not None and not count.group(1):
        form = f"{form[: count.start()]}%{match.group(1)}${form[count.start() + 1 :]}"
    return format_key[: match.start()] + form + format_key[match.end() :]


def _specifiers(pattern: re.Pattern, value: str) -> list[str]:
    return [m.group(0) for m in pattern.finditer(value) if m.group(0) != "%%"]


def _first(pattern: re.Pattern, value: str) -> re.Match | None:
    return next((m for m in pattern.finditer(value) if m.group(0) != "%%"), None)


def _replace_first(pattern: re.Pattern, value: str, replacement: str) -> str:
    match = _first(pattern, value)
    if match is None:
        return value
    return value[: match.start()] + replacement + value[match.end() :]
