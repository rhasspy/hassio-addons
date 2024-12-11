import math
from collections import defaultdict, deque
from dataclasses import dataclass, field
from functools import reduce
from typing import Dict, List, Optional, Set, TextIO, Tuple

from unicode_rbnf import RbnfEngine

from .intents import (
    Intents,
    IntentData,
    SlotList,
    TextSlotList,
    RangeSlotList,
    WildcardSlotList,
)
from .expression import (
    Expression,
    ListReference,
    RuleReference,
    TextChunk,
    Sequence,
    SequenceType,
    Sentence,
)
from .util import check_excluded_context, check_required_context

EPS = "<eps>"
SPACE = "<space>"


@dataclass
class FstArc:
    to_state: int
    in_label: str = EPS
    out_label: str = EPS
    log_prob: Optional[float] = None


@dataclass
class Fst:
    arcs: Dict[int, List[FstArc]] = field(default_factory=lambda: defaultdict(list))
    final_states: Set[int] = field(default_factory=set)
    start: int = 0
    current_state: int = 0

    def next_state(self) -> int:
        self.current_state += 1
        return self.current_state

    def next_edge(
        self,
        from_state: int,
        in_label: Optional[str] = None,
        out_label: Optional[str] = None,
        log_prob: Optional[float] = None,
    ) -> int:
        to_state = self.next_state()
        self.add_edge(from_state, to_state, in_label, out_label, log_prob)
        return to_state

    def add_edge(
        self,
        from_state: int,
        to_state: int,
        in_label: Optional[str] = None,
        out_label: Optional[str] = None,
        log_prob: Optional[float] = None,
    ) -> None:
        if in_label is None:
            in_label = EPS

        if out_label is None:
            out_label = in_label

        if (" " in in_label) or (" " in out_label):
            raise ValueError(
                f"Cannot have white space in labels: from={in_label}, to={out_label}"
            )

        if (not in_label) or (not out_label):
            raise ValueError(f"Labels cannot be empty: from={in_label}, to={out_label}")

        self.arcs[from_state].append(FstArc(to_state, in_label, out_label, log_prob))

    def accept(self, state: int) -> None:
        self.final_states.add(state)

    def write(self, fst_file: TextIO, symbols_file: TextIO) -> None:
        symbols = {EPS: 0}

        for state, arcs in self.arcs.items():
            for arc in arcs:
                if arc.in_label not in symbols:
                    symbols[arc.in_label] = len(symbols)

                if arc.out_label not in symbols:
                    symbols[arc.out_label] = len(symbols)

                if arc.log_prob is None:
                    print(
                        state, arc.to_state, arc.in_label, arc.out_label, file=fst_file
                    )
                else:
                    print(
                        state,
                        arc.to_state,
                        arc.in_label,
                        arc.out_label,
                        arc.log_prob,
                        file=fst_file,
                    )

        for state in self.final_states:
            print(state, file=fst_file)

        for symbol, symbol_id in symbols.items():
            print(symbol, symbol_id, file=symbols_file)

    def replace(self, replacements: "Dict[str, Fst]") -> "Fst":
        pass

    def remove_spaces(self) -> "Fst":
        fst_no_spaces = Fst()
        q = deque([(self.start, fst_no_spaces.start, [])])

        while q:
            state, next_state, word_parts = q.popleft()
            is_final = state in self.final_states

            if is_final and word_parts:
                word = "".join(word_parts)
                fst_no_spaces.accept(fst_no_spaces.next_edge(next_state, word, word))

            for arc in self.arcs[state]:
                if arc.in_label == SPACE:
                    # End word
                    if word_parts:
                        word = "".join(word_parts)
                        q.append(
                            (
                                arc.to_state,
                                fst_no_spaces.next_edge(next_state, word, word),
                                [],
                            )
                        )
                    else:
                        q.append((arc.to_state, next_state, []))
                else:
                    # Continue word
                    if arc.in_label != EPS:
                        q.append(
                            (arc.to_state, next_state, word_parts + [arc.in_label])
                        )
                    else:
                        q.append((arc.to_state, next_state, word_parts))

        return fst_no_spaces


@dataclass
class NumToWords:
    engine: RbnfEngine
    cache: Dict[Tuple[int, int, int], Sequence] = field(default_factory=dict)


def expression_to_fst(
    expression: Expression,
    state: int,
    fst: Fst,
    intent_data: IntentData,
    intents: Intents,
    slot_lists: Optional[Dict[str, SlotList]] = None,
    num_to_words: Optional[NumToWords] = None,
) -> int:
    if isinstance(expression, TextChunk):
        chunk: TextChunk = expression

        space_before = False
        space_after = False

        if chunk.original_text == " ":
            return fst.next_edge(state, SPACE)

        if chunk.original_text.startswith(" "):
            space_before = True

        if chunk.original_text.endswith(" "):
            space_after = True

        word = chunk.original_text.strip()
        if not word:
            return state

        if space_before:
            state = fst.next_edge(state, SPACE)

        sub_words = word.split()
        last_sub_word_idx = len(sub_words) - 1
        for sub_word_idx, sub_word in enumerate(sub_words):
            state = fst.next_edge(state, sub_word)
            if sub_word_idx != last_sub_word_idx:
                # Add spaces between words
                state = fst.next_edge(state, SPACE)

        if space_after:
            state = fst.next_edge(state, SPACE)

        return state

    if isinstance(expression, Sequence):
        seq: Sequence = expression
        if seq.type == SequenceType.ALTERNATIVE:
            start = state
            end = fst.next_state()

            for item in seq.items:
                state = expression_to_fst(
                    item, start, fst, intent_data, intents, slot_lists, num_to_words
                )
                if state == start:
                    # Empty item
                    continue

                fst.add_edge(state, end)

            if seq.is_optional:
                fst.add_edge(start, end)

            return end

        if seq.type == SequenceType.GROUP:
            for item in seq.items:
                state = expression_to_fst(
                    item, state, fst, intent_data, intents, slot_lists, num_to_words
                )

            return state

    if isinstance(expression, ListReference):
        # {list}
        list_ref: ListReference = expression

        slot_list: Optional[SlotList] = None
        if slot_lists is not None:
            slot_list = slot_lists.get(list_ref.list_name)

        if slot_list is None:
            slot_list = intent_data.slot_lists.get(list_ref.list_name)

        if slot_list is None:
            slot_list = intents.slot_lists.get(list_ref.list_name)

        if isinstance(slot_list, TextSlotList):
            text_list: TextSlotList = slot_list

            values = []
            for value in text_list.values:
                if (intent_data.requires_context is not None) and (
                    not check_required_context(
                        intent_data.requires_context,
                        value.context,
                        allow_missing_keys=True,
                    )
                ):
                    continue

                if (intent_data.excludes_context is not None) and (
                    not check_excluded_context(
                        intent_data.excludes_context,
                        value.context,
                    )
                ):
                    continue

                values.append(value.text_in)

            if values:
                return expression_to_fst(
                    Sequence(values, type=SequenceType.ALTERNATIVE),
                    state,
                    fst,
                    intent_data,
                    intents,
                    slot_lists,
                    num_to_words,
                )

        elif isinstance(slot_list, RangeSlotList):
            range_list: RangeSlotList = slot_list
            number_sequence: Optional[Sequence] = None
            num_cache_key = (range_list.start, range_list.stop + 1, range_list.step)

            if num_to_words is not None:
                number_sequence = num_to_words.cache.get(num_cache_key)

            if number_sequence is None:
                values = []
                # TODO
                # for number in range(
                #     range_list.start, range_list.stop + 1, range_list.step
                # ):
                #     values.append(TextChunk(str(number)))

                if num_to_words is not None:
                    for number in range(
                        range_list.start, range_list.stop + 1, range_list.step
                    ):
                        number_result = num_to_words.engine.format_number(number)
                        number_words = {
                            w.replace("-", " ")
                            for w in number_result.text_by_ruleset.values()
                        }
                        values.extend((TextChunk(w) for w in number_words))

                number_sequence = Sequence(values, type=SequenceType.ALTERNATIVE)

                if num_to_words is not None:
                    num_to_words.cache[num_cache_key] = number_sequence

            return expression_to_fst(
                number_sequence,
                state,
                fst,
                intent_data,
                intents,
                slot_lists,
                num_to_words,
            )
        else:
            word = f"{{{list_ref.list_name}}}"
            return expression_to_fst(
                TextChunk(word),
                state,
                fst,
                intent_data,
                intents,
                slot_lists,
                num_to_words,
            )

    if isinstance(expression, RuleReference):
        # <rule>
        rule_ref: RuleReference = expression

        rule_body: Optional[Sentence] = intent_data.expansion_rules.get(
            rule_ref.rule_name
        )
        if rule_body is None:
            rule_body = intents.expansion_rules.get(rule_ref.rule_name)

        if rule_body is None:
            raise ValueError(f"Missing expansion rule <{rule_ref.rule_name}>")

        return expression_to_fst(
            rule_body, state, fst, intent_data, intents, slot_lists, num_to_words
        )

    return state


def get_count(
    e: Expression,
    intents: Intents,
    intent_data: IntentData,
) -> int:
    if isinstance(e, Sequence):
        seq: Sequence = e
        item_counts = [get_count(item, intents, intent_data) for item in seq.items]

        if seq.type == SequenceType.ALTERNATIVE:
            return sum(item_counts)

        if seq.type == SequenceType.GROUP:
            return reduce(lambda x, y: x * y, item_counts, 1)

    if isinstance(e, ListReference):
        list_ref: ListReference = e
        slot_list: Optional[SlotList] = None

        slot_list = intent_data.slot_lists.get(list_ref.list_name)
        if not slot_list:
            slot_list = intents.slot_lists.get(list_ref.list_name)

        if isinstance(slot_list, TextSlotList):
            text_list: TextSlotList = slot_list
            return sum(
                get_count(v.text_in, intents, intent_data) for v in text_list.values
            )

        if isinstance(slot_list, RangeSlotList):
            range_list: RangeSlotList = slot_list
            if range_list.step == 1:
                return range_list.stop - range_list.start + 1

            return len(range(range_list.start, range_list.stop + 1, range_list.step))

    if isinstance(e, RuleReference):
        rule_ref: RuleReference = e
        rule_body: Optional[Sentence] = None

        rule_body = intent_data.expansion_rules.get(rule_ref.rule_name)
        if not rule_body:
            rule_body = intents.expansion_rules.get(rule_ref.rule_name)

        if rule_body:
            return get_count(rule_body, intents, intent_data)

    return 1


def lcm(*nums: int) -> int:
    """Returns the least common multiple of the given integers"""
    if nums:
        nums_lcm = nums[0]
        for n in nums[1:]:
            nums_lcm = (nums_lcm * n) // math.gcd(nums_lcm, n)

        return nums_lcm

    return 1


def intents_to_fst(
    intents: Intents,
    slot_lists: Optional[Dict[str, SlotList]] = None,
    number_language: Optional[str] = None,
    exclude_intents: Optional[Set[str]] = None,
    include_intents: Optional[Set[str]] = None,
) -> Fst:
    num_to_words: Optional[NumToWords] = None
    if number_language:
        num_to_words = NumToWords(engine=RbnfEngine.for_language(number_language))

    filtered_intents = []
    # sentence_counts: Dict[str, int] = {}
    sentence_counts: Dict[Sentence, int] = {}

    for intent in intents.intents.values():
        if (exclude_intents is not None) and (intent.name in exclude_intents):
            continue

        if (include_intents is not None) and (intent.name not in include_intents):
            continue

        # num_sentences = 0
        for i, data in enumerate(intent.data):
            for j, sentence in enumerate(data.sentences):
                # num_sentences += get_count(sentence, intents, data)
                sentence_counts[(intent.name, i, j)] = get_count(
                    sentence, intents, data
                )

        filtered_intents.append(intent)
        # sentence_counts[intent.name] = num_sentences

    fst_with_spaces = Fst()
    final = fst_with_spaces.next_state()

    num_sentences_lcm = lcm(*sentence_counts.values())
    # intent_weights = {
    #     intent_name: num_sentences_lcm // max(1, count)
    #     for intent_name, count in sentence_counts.items()
    # }
    # weight_sum = max(1, sum(intent_weights.values()))
    # total_sentences = max(1, sum(sentence_counts.values()))

    sentence_weights = {
        key: num_sentences_lcm // max(1, count)
        for key, count in sentence_counts.items()
    }
    weight_sum = max(1, sum(sentence_weights.values()))

    for intent in filtered_intents:
        # weight = intent_weights[intent.name] / weight_sum
        # weight = 1 / len(filtered_intents)
        # print(intent.name, weight)
        # intent_prob = -math.log(weight)
        # intent_state = fst_with_spaces.next_edge(
        #     fst_with_spaces.start, SPACE, SPACE, #log_prob=intent_prob
        # )

        for i, data in enumerate(intent.data):
            for j, sentence in enumerate(data.sentences):
                weight = sentence_weights[(intent.name, i, j)]
                sentence_prob = weight / weight_sum
                # print(sentence.text, sentence_prob)
                sentence_state = fst_with_spaces.next_edge(
                    fst_with_spaces.start,
                    SPACE,
                    SPACE,
                    # log_prob=-math.log(sentence_prob),
                )
                state = expression_to_fst(
                    sentence,
                    # intent_state,
                    sentence_state,
                    fst_with_spaces,
                    data,
                    intents,
                    slot_lists,
                    num_to_words,
                )
                fst_with_spaces.add_edge(state, final)

    fst_with_spaces.accept(final)

    return fst_with_spaces
