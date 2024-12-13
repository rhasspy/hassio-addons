import base64
import itertools
import json
from collections import defaultdict
from collections.abc import Iterable
from functools import partial
from typing import Dict, List, Optional, cast

from hassil.expression import (
    Expression,
    ListReference,
    RuleReference,
    Sentence,
    Sequence,
    SequenceType,
    TextChunk,
)
from hassil.intents import (
    IntentData,
    Intents,
    RangeSlotList,
    SlotList,
    TextSlotList,
    TextSlotValue,
)
from hassil.util import (
    check_excluded_context,
    check_required_context,
    normalize_whitespace,
)


def sample_intents(intents: Intents) -> Dict[str, Dict[int, List[str]]]:
    """Sample text strings for sentences from intents."""
    sentences: Dict[str, Dict[int, List[str]]] = defaultdict(lambda: defaultdict(list))

    for intent_name, intent in sorted(intents.intents.items(), key=lambda kv: kv[0]):
        for group_idx, intent_data in enumerate(intent.data):
            for intent_sentence in sorted(
                intent_data.sentences, key=lambda s: s.text or ""
            ):
                sentence_texts = sample_expression(
                    intent_sentence, intent_data, intents
                )
                for sentence_text in sorted(sentence_texts):
                    sentences[intent_name][group_idx].append(sentence_text)

    return sentences


def sample_expression(
    expression: Expression,
    intent_data: IntentData,
    intents: Intents,
    in_list_value: bool = False,
) -> Iterable[str]:
    """Sample possible text strings from an expression."""
    if isinstance(expression, TextChunk):
        chunk: TextChunk = expression
        yield chunk.original_text
    elif isinstance(expression, Sequence):
        seq: Sequence = expression
        if seq.is_optional and (not in_list_value):
            yield ""
        elif seq.type == SequenceType.ALTERNATIVE:
            # Try to compact to/show/alternatives
            is_all_text = True
            text_alternatives: List[str] = []
            for item in seq.items:
                if isinstance(item, TextChunk):
                    text_alternatives.append(item.original_text.strip())
                    continue

                # Unpack max two levels
                if (
                    isinstance(item, Sequence)
                    and (item.type == SequenceType.GROUP)
                    and all(isinstance(sub_item, TextChunk) for sub_item in item.items)
                ):
                    text_alternatives.append(
                        " ".join(
                            cast(TextChunk, sub_item).text for sub_item in item.items
                        )
                    )
                    continue

                is_all_text = False
                break

            if is_all_text and all(text.strip() for text in text_alternatives):
                # Add slashes if all of the items are non-empty text strings
                if any(" " in text for text in text_alternatives):
                    yield "(" + "/".join(sorted(text_alternatives)) + ")"
                else:
                    yield "/".join(sorted(text_alternatives))
            else:
                for item in seq.items:
                    yield from sample_expression(
                        item, intent_data, intents, in_list_value=in_list_value
                    )
        elif seq.type == SequenceType.GROUP:
            seq_sentences = map(
                partial(
                    sample_expression,
                    intent_data=intent_data,
                    intents=intents,
                    in_list_value=in_list_value,
                ),
                seq.items,
            )
            sentence_texts = itertools.product(*seq_sentences)
            for sentence_words in sentence_texts:
                yield normalize_whitespace("".join(sentence_words))
    elif isinstance(expression, ListReference):
        # {list}
        list_ref: ListReference = expression

        slot_list: Optional[SlotList] = intent_data.slot_lists.get(list_ref.list_name)

        if slot_list is None:
            slot_list = intents.slot_lists.get(list_ref.list_name)

        if isinstance(slot_list, TextSlotList):
            text_list: TextSlotList = slot_list

            # Filter by context
            sorted_values = sorted(
                text_list.values,
                key=lambda v: (
                    v.text_in.text
                    if isinstance(v.text_in, TextChunk)
                    else str(v.text_in)
                ),
            )
            possible_values: List[TextSlotValue] = []
            if intent_data.requires_context or intent_data.excludes_context:
                for value in sorted_values:
                    if not value.context:
                        possible_values.append(value)
                        continue

                    if intent_data.requires_context and (
                        not check_required_context(
                            intent_data.requires_context,
                            value.context,
                            allow_missing_keys=True,
                        )
                    ):
                        continue

                    if intent_data.excludes_context and (
                        not check_excluded_context(
                            intent_data.excludes_context, value.context
                        )
                    ):
                        continue

                    possible_values.append(value)
            else:
                possible_values = sorted_values

            value_texts = []
            for value in possible_values:
                for value_text in sample_expression(
                    value.text_in, intent_data, intents, in_list_value=True
                ):
                    value_texts.append(value_text)

            if value_texts:
                yield "__list:" + base64.b64encode(
                    json.dumps(value_texts).encode("utf-8")
                ).decode("utf-8").strip()
            else:
                yield f"{{{list_ref.list_name}}}"
        elif isinstance(slot_list, RangeSlotList):
            range_list: RangeSlotList = slot_list

            yield f"__number:{range_list.start},{range_list.stop+1},{range_list.step}"
        else:
            yield f"{{{list_ref.list_name}}}"
    elif isinstance(expression, RuleReference):
        # <rule>
        rule_ref: RuleReference = expression

        rule_body: Optional[Sentence] = intent_data.expansion_rules.get(
            rule_ref.rule_name
        )
        if rule_body is None:
            rule_body = intents.expansion_rules.get(rule_ref.rule_name)

        if rule_body is not None:
            yield from sample_expression(
                rule_body, intent_data, intents, in_list_value=in_list_value
            )
        else:
            yield f"<{rule_ref.rule_name}>"
    else:
        yield ""
