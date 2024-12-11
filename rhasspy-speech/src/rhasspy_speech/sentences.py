import collections.abc
import itertools
import logging
import time
from collections.abc import Iterable
from collections.abc import Sequence as ABCSequence
from functools import partial
from typing import Any, Dict, List, Optional, Tuple

import hassil.parse_expression
import hassil.sample
from hassil.errors import MissingListError, MissingRuleError
from hassil.expression import (
    Expression,
    ListReference,
    RuleReference,
    Sentence,
    Sequence,
    SequenceType,
    TextChunk,
)
from hassil.intents import SlotList, TextSlotList, TextSlotValue
from hassil.util import normalize_whitespace
from unicode_rbnf import RbnfEngine

_LOGGER = logging.getLogger()


def generate_sentences(
    sentences_yaml: Dict[str, Any], number_engine: Optional[RbnfEngine] = None
) -> Iterable[Tuple[str, str]]:
    start_time = time.monotonic()

    # sentences:
    #   - same text in and out
    #   - in: text in
    #     out: different text out
    #   - in:
    #       - multiple text
    #       - multiple text in
    #     out: different text out
    # lists:
    #   <name>:
    #     - value 1
    #     - value 2
    # expansion_rules:
    #   <name>: sentence template
    templates = sentences_yaml["sentences"]

    # Load slot lists
    slot_lists: Dict[str, SlotList] = {}
    for slot_name, slot_info in sentences_yaml.get("lists", {}).items():
        if isinstance(slot_info, ABCSequence):
            slot_info = {"values": slot_info}

        slot_list_values: List[TextSlotValue] = []

        slot_range = slot_info.get("range")
        if slot_range:
            assert (
                number_engine is not None
            ), "Can't expand ranges without a number engine"
            slot_from = int(slot_range["from"])
            slot_to = int(slot_range["to"])
            slot_step = int(slot_range.get("step", 1))
            for i in range(slot_from, slot_to + 1, slot_step):
                # Use all available words for a number (all genders, cases, etc.)
                format_result = number_engine.format_number(i)
                number_strs = {
                    s.replace("-", " ") for s in format_result.text_by_ruleset.values()
                }
                slot_list_values.extend(
                    (
                        TextSlotValue(
                            text_in=TextChunk(number_str),
                            value_out=i,
                        )
                        for number_str in number_strs
                    )
                )

            slot_lists[slot_name] = TextSlotList(
                name=slot_name, values=slot_list_values
            )
            continue

        slot_values = slot_info.get("values")
        if not slot_values:
            _LOGGER.warning("No values for list %s, skipping", slot_name)
            continue

        for slot_value in slot_values:
            values_in: List[str] = []
            values_out: List[str] = []

            if isinstance(slot_value, str):
                slot_value = {"in": slot_value}

            # - in: text to say
            #   out: text to output
            value_in = str(slot_value["in"])
            if not value_in:
                # Skip slot value
                continue

            value_out = slot_value.get("out")
            value_context = slot_value.get("context")

            if hassil.intents.is_template(value_in):
                input_expression = hassil.parse_expression.parse_sentence(value_in)
                for input_text in hassil.sample.sample_expression(
                    input_expression,
                ):
                    values_in.append(input_text)
                    values_out.append(value_out or input_text)
            else:
                values_in.append(value_in)
                values_out.append(value_out or value_in)

            for value_in, value_out in zip(values_in, values_out):
                slot_list_values.append(
                    TextSlotValue(
                        TextChunk(value_in), value_out=value_out, context=value_context
                    )
                )

        slot_lists[slot_name] = TextSlotList(name=slot_name, values=slot_list_values)

    # Load expansion rules
    expansion_rules: Dict[str, hassil.Sentence] = {}
    for rule_name, rule_text in sentences_yaml.get("expansion_rules", {}).items():
        expansion_rules[rule_name] = hassil.parse_sentence(rule_text)

    # Generate possible sentences
    num_sentences = 0
    for template in templates:
        requires_context: Optional[Dict[str, Any]] = None
        excludes_context: Optional[Dict[str, Any]] = None

        if isinstance(template, str):
            input_templates: List[str] = [template]
            output_text: Optional[str] = None
        else:
            input_str_or_list = template["in"]
            if isinstance(input_str_or_list, str):
                # One template
                input_templates = [input_str_or_list]
            else:
                # Multiple templates
                input_templates = input_str_or_list

            output_text = template.get("out")
            requires_context = template.get("requires_context")
            excludes_context = template.get("excludes_context")

        for input_template in input_templates:
            if hassil.intents.is_template(input_template):
                # Generate possible texts
                input_expression = hassil.parse_expression.parse_sentence(
                    input_template
                )
                for (
                    input_text,
                    maybe_output_text,
                    list_values,
                ) in sample_expression_with_output(
                    input_expression,
                    slot_lists=slot_lists,
                    expansion_rules=expansion_rules,
                    requires_context=requires_context,
                    excludes_context=excludes_context,
                ):
                    if output_text is None:
                        final_output_text = maybe_output_text or input_text
                    else:
                        # May be empty
                        final_output_text = output_text

                    if list_values:
                        # Replace {lists} with values
                        final_output_text = final_output_text.format(**list_values)

                    yield (input_text, final_output_text)
                    num_sentences += 1
            else:
                # Not a template
                if output_text is None:
                    final_output_text = input_template
                else:
                    # May be empty
                    final_output_text = output_text

                yield (input_template, final_output_text)
                num_sentences += 1

    end_time = time.monotonic()

    _LOGGER.info(
        "Generated %s sentence(s) with in %0.2f second(s)",
        num_sentences,
        end_time - start_time,
    )


def sample_expression_with_output(
    expression: Expression,
    slot_lists: Optional[Dict[str, SlotList]] = None,
    expansion_rules: Optional[Dict[str, Sentence]] = None,
    list_values: Optional[Dict[str, Any]] = None,
    requires_context: Optional[Dict[str, Any]] = None,
    excludes_context: Optional[Dict[str, Any]] = None,
) -> Iterable[Tuple[str, Optional[str], Dict[str, Any]]]:
    """Sample possible text strings from an expression."""
    if list_values is None:
        list_values = {}

    if isinstance(expression, TextChunk):
        chunk: TextChunk = expression
        yield (chunk.original_text, chunk.original_text, list_values)
    elif isinstance(expression, Sequence):
        seq: Sequence = expression
        if seq.type == SequenceType.ALTERNATIVE:
            for item in seq.items:
                yield from sample_expression_with_output(
                    item,
                    slot_lists,
                    expansion_rules,
                    list_values,
                    requires_context,
                    excludes_context,
                )
        elif seq.type == SequenceType.GROUP:
            seq_sentences = map(
                partial(
                    sample_expression_with_output,
                    slot_lists=slot_lists,
                    expansion_rules=expansion_rules,
                    list_values=list_values,
                    requires_context=requires_context,
                    excludes_context=excludes_context,
                ),
                seq.items,
            )
            sentence_texts = itertools.product(*seq_sentences)

            # sentence_words = [(input_text, output_text, list_values), ...]
            for sentence_words in sentence_texts:
                # Merge list values
                sentence_list_values = dict(list_values)
                for word in sentence_words:
                    sentence_list_values.update(word[2])

                yield (
                    normalize_whitespace("".join(w[0] for w in sentence_words)),
                    normalize_whitespace(
                        "".join(str(w[1]) for w in sentence_words if w[1] is not None)
                    ),
                    sentence_list_values,
                )
        else:
            raise ValueError(f"Unexpected sequence type: {seq}")
    elif isinstance(expression, ListReference):
        # {list}
        list_ref: ListReference = expression
        if (not slot_lists) or (list_ref.list_name not in slot_lists):
            raise MissingListError(f"Missing slot list {{{list_ref.list_name}}}")

        slot_list = slot_lists[list_ref.list_name]
        if isinstance(slot_list, TextSlotList):
            text_list: TextSlotList = slot_list

            if requires_context or excludes_context:
                # Filtered values
                filtered_values = [
                    v
                    for v in text_list.values
                    if (
                        (not requires_context)
                        or check_required_context(
                            requires_context, v.context, allow_missing_keys=True
                        )
                    )
                    and (
                        (not excludes_context)
                        or check_excluded_context(excludes_context, v.context)
                    )
                ]
            else:
                filtered_values = text_list.values

            if not filtered_values:
                # Not necessarily an error, but may be a surprise
                _LOGGER.warning("No values for list: %s", list_ref.list_name)

            for text_value in filtered_values:
                for (
                    value_input_text,
                    value_output_text,
                    value_list_values,
                ) in sample_expression_with_output(
                    text_value.text_in,
                    slot_lists,
                    expansion_rules,
                    list_values,
                    requires_context,
                    excludes_context,
                ):
                    value_output_text = text_value.value_out or value_output_text
                    yield (
                        value_input_text,
                        text_value.value_out or value_output_text,
                        {
                            **value_list_values,
                            **{list_ref.list_name: value_output_text},
                        },
                    )
        else:
            # Range lists are expanded into words earlier.
            # Wildcards are not supported.
            raise ValueError(f"Unexpected slot list type: {slot_list}")
    elif isinstance(expression, RuleReference):
        # <rule>
        rule_ref: RuleReference = expression
        if (not expansion_rules) or (rule_ref.rule_name not in expansion_rules):
            raise MissingRuleError(f"Missing expansion rule <{rule_ref.rule_name}>")

        rule_body = expansion_rules[rule_ref.rule_name]
        yield from sample_expression_with_output(
            rule_body,
            slot_lists,
            expansion_rules,
            list_values,
            requires_context,
            excludes_context,
        )
    else:
        raise ValueError(f"Unexpected expression: {expression}")


def check_required_context(
    required_context: Dict[str, Any],
    match_context: Optional[Dict[str, Any]],
    allow_missing_keys: bool = False,
) -> bool:
    """Return True if match context does not violate required context.

    Setting allow_missing_keys to True only checks existing keys in match
    context.
    """
    for (
        required_key,
        required_value,
    ) in required_context.items():
        if (not match_context) or (required_key not in match_context):
            # Match is missing key
            if allow_missing_keys:
                # Only checking existing keys
                continue

            return False

        if isinstance(required_value, collections.abc.Mapping):
            # Unpack dict
            # <context_key>:
            #   value: ...
            required_value = required_value.get("value")

        # Ensure value matches
        actual_value = match_context[required_key]

        if isinstance(actual_value, collections.abc.Mapping):
            # Unpack dict
            # <context_key>:
            #   value: ...
            actual_value = actual_value.get("value")

        if (not isinstance(required_value, str)) and isinstance(
            required_value, collections.abc.Collection
        ):
            if actual_value not in required_value:
                # Match value not in required list
                return False
        elif (required_value is not None) and (actual_value != required_value):
            # Match value doesn't equal required value
            return False

    return True


def check_excluded_context(
    excluded_context: Dict[str, Any], match_context: Optional[Dict[str, Any]]
) -> bool:
    """Return True if match context does not violate excluded context."""
    for (
        excluded_key,
        excluded_value,
    ) in excluded_context.items():
        if (not match_context) or (excluded_key not in match_context):
            continue

        if isinstance(excluded_value, collections.abc.Mapping):
            # Unpack dict
            # <context_key>:
            #   value: ...
            excluded_value = excluded_value.get("value")

        # Ensure value does not match
        actual_value = match_context[excluded_key]

        if isinstance(actual_value, collections.abc.Mapping):
            # Unpack dict
            # <context_key>:
            #   value: ...
            actual_value = actual_value.get("value")

        if (not isinstance(excluded_value, str)) and isinstance(
            excluded_value, collections.abc.Collection
        ):
            if actual_value in excluded_value:
                # Match value is in excluded list
                return False
        elif actual_value == excluded_value:
            # Match value equals excluded value
            return False

    return True
