#
# JiWER - Jitsi Word Error Rate
#
# Copyright @ 2018 - present 8x8, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

"""
This file implements methods for calculating a number of similarity error
measures between a ground-truth sentence and a hypothesis sentence, which are
commonly used to measure the performance for an automatic speech recognition
(ASR) system.

The following measures are implemented:

- Word Error Rate (WER), which is where this library got its name from. This
  has has long been (and arguably still is) the de facto standard for computing
  ASR performance.
- Match Error Rate (MER)
- Word Information Lost (WIL)
- Word Information Preserved (WIP)
"""
import warnings

import Levenshtein

from typing import Any, Dict, List, Tuple, Union
from itertools import chain

from jiwer import transforms as tr
from jiwer.transformations import wer_default, wer_standardize, cer_default_transform

__all__ = [
    "wer",
    "mer",
    "wil",
    "wip",
    "cer",
    "compute_measures",
]

################################################################################
# 

class words_alignment_inf:
    def __init__(self):
      self.reset()

    def reset(self):
        self.collect_information = False
        self.vocabulary = None
        self.word2char = None
        self.char2word = None
        self.editops = list()
        self.truth = None
        self.hypothesis = None

        # detailed errors information
        self.TruthWordsCount = dict()
        self.Correct = None
        self.Insersions = None
        self.Deletions = None
        self.Substitutions = None

    def collect(self):
        self.reset()
        self.collect_information = True

    def set_vocabulary(self, vocabulary):
        if self.collect_information:
            self.vocabulary = vocabulary

    def set_word2char(self, word2char):
        if self.collect_information:
            self.word2char = word2char

    def set_truth_hypothesis(self, truth, hypothesis):
        if not self.collect_information:
            return

        self.truth = truth
        self.hypothesis = hypothesis

        # truth words count
        for sentence in self.truth:
          for w in sentence:
              if w not in self.TruthWordsCount:
                self.TruthWordsCount[w] = 0
              self.TruthWordsCount[w] += 1

    def add_editops(self, editops):
        if self.collect_information:
            self.editops.append(editops)

    def validate(self):
      if not self.collect_information:
        return
      assert (self.editops is not [])
      assert (self.vocabulary is not None)
      assert (self.word2char is not None)
      assert (self.truth is not None)
      assert (self.hypothesis is not None)

    def collect_errors_information(self, *, print_alignment=True):
      # create inverse dictionary
      self.char2word =  {value:key for (key,value) in self.word2char.items()}

      self.Insersions = dict()
      self.Deletions = dict()
      self.Substitutions = dict()

      for i, (groundtruth, hypothesis) in enumerate(zip(self.truth, self.hypothesis)):
        if print_alignment:
          print(f"\n### sentence {i:>3}, truth length:{len(groundtruth):>3}, hyp lenngth{len(hypothesis):>3}")

        ref_true_pos, ref_hyp_pos = 0, 0
        for (op, op_true_pos, op_hyp_pos)  in self.editops[i]:
            
            keepOn = True
            while keepOn:

                if (op == 'replace' and 
                    ref_true_pos == op_true_pos and
                    ref_hyp_pos == op_hyp_pos):
                  
                    key = (groundtruth[ref_true_pos], hypothesis[ref_hyp_pos])
                    if key not in self.Substitutions:
                      self.Substitutions[key] = 0
                    self.Substitutions[key] += 1

                    if print_alignment:
                      ref_word = self.char2word[ord(groundtruth[ref_true_pos])]
                      hyp_word = self.char2word[ord(hypothesis[ref_hyp_pos])]
                      print(f"{ref_true_pos:>3} {ref_word:<10} {ref_hyp_pos:>3} {hyp_word:<10} 'SUB'")

                    ref_true_pos += 1
                    ref_hyp_pos += 1
                    keepOn = False

                elif (op == 'delete' and 
                      ref_true_pos == op_true_pos):

                    if groundtruth[ref_true_pos] not in self.Deletions:
                      self.Deletions[groundtruth[ref_true_pos]] = 0
                    self.Deletions[groundtruth[ref_true_pos]] += 1

                    if print_alignment:
                      ref_word = self.char2word[ord(groundtruth[ref_true_pos])]
                      print(f"{ref_true_pos:>3} {ref_word:<10} {'-':>3} {'-':<10} 'DEL'")

                    ref_true_pos += 1
                    keepOn = False
                    
                elif (op == 'insert' and 
                      ref_hyp_pos == op_hyp_pos):
                  
                    if hypothesis[ref_hyp_pos] not in self.Insersions:
                      self.Insersions[hypothesis[ref_hyp_pos]] = 0
                    self.Insersions[hypothesis[ref_hyp_pos]] += 1

                    if print_alignment:
                      hyp_word = self.char2word[ord(hypothesis[ref_hyp_pos])]
                      print(f"{'-':>3} {'-':<10} {ref_hyp_pos:>3} {hyp_word:<10} 'INS'")

                    ref_hyp_pos += 1
                    keepOn = False

                elif ref_true_pos<=op_true_pos:
                    if print_alignment:
                      ref_word = self.char2word[ord(groundtruth[ref_true_pos])]
                      hyp_word = self.char2word[ord(hypothesis[ref_hyp_pos])]
                      print(f"{ref_true_pos:>3} {ref_word:<10} {ref_hyp_pos:>3} {hyp_word:<10} 'COR'")

                    ref_true_pos += 1
                    ref_hyp_pos += 1 

                else:
                    raise Exception("Unsupported editops. potential code bug.")


    def print_analysis(self):
      assert (self.collect_information)

      print("\n------------------------------------------")
      print("Detailed recognition performance analysis.")
      print("")
      print("Truth words count.")
      sorted_keys = sorted(self.TruthWordsCount, 
                           key=self.TruthWordsCount.get,
                           reverse=True)

      assert self.char2word is not None,  "call collect_errors_information() before print_analysis()"

      for w in sorted_keys:
        word = self.char2word[ord(w)]
        value = self.TruthWordsCount[w]
        print(f"{word:<10} {value:>5d}")

      print("")
      print("Deletions words count.")
      sorted_keys = sorted(self.Deletions, 
                           key=self.Deletions.get,
                           reverse=True)
      for w in sorted_keys:
        word = self.char2word[ord(w)]
        value = self.Deletions[w]
        print(f"{word:<10} {value:>5d}")

      print("")
      print("Insersions words count.")
      sorted_keys = sorted(self.Insersions, 
                           key=self.Insersions.get,
                           reverse=True)
      for w in sorted_keys:
        word = self.char2word[ord(w)]
        value = self.Insersions[w]
        print(f"{word:<10} {value:>5d}")

      print("")
      print("Substitutions words count.")
      sorted_keys = sorted(self.Substitutions, 
                           key=self.Substitutions.get,
                           reverse=True)
      print(f'{("True-word").ljust(10)} {("Hyp-word").ljust(10)} {("Count").rjust(5)}')
      for w in sorted_keys:
        true_w, hyp_w = w
        true_word = self.char2word[ord(true_w)]
        hyp_word = self.char2word[ord(hyp_w)]
        value = self.Substitutions[w]
        print(f"{true_word:<10} {hyp_word:<10} {value:>5d}")

# local 
words_alignment = words_alignment_inf()

################################################################################
# Implementation of the WER method and co, exposed publicly


def wer(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    get_alignment: bool = False,
    **kwargs
) -> float:
    """
    Calculate word error rate (WER) between a set of ground-truth sentences and
    a set of hypothesis sentences.

    See `compute_measures` for details on the arguments.

    :return: WER as a floating point number
    """

    words_alignment.reset()
    if get_alignment:
      words_alignment.collect()

    measures = compute_measures(
        truth, hypothesis, truth_transform, hypothesis_transform, **kwargs
    )
    return measures["wer"]


def mer(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    **kwargs
) -> float:
    """
    Calculate match error rate (MER) between a set of ground-truth sentences and
    a set of hypothesis sentences.

    See `compute_measures` for details on the arguments.

    :return: MER as a floating point number
    """
    measures = compute_measures(
        truth, hypothesis, truth_transform, hypothesis_transform, **kwargs
    )
    return measures["mer"]


def wip(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    **kwargs
) -> float:
    """
    Calculate Word Information Preserved (WIP) between a set of ground-truth
    sentences and a set of hypothesis sentences.

    See `compute_measures` for details on the arguments.

    :return: WIP as a floating point number
    """
    measures = compute_measures(
        truth, hypothesis, truth_transform, hypothesis_transform, **kwargs
    )
    return measures["wip"]


def wil(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    **kwargs
) -> float:
    """
    Calculate Word Information Lost (WIL) between a set of ground-truth sentences
    and a set of hypothesis sentences.

    See `compute_measures` for details on the arguments.

    :return: WIL as a floating point number
    """
    measures = compute_measures(
        truth, hypothesis, truth_transform, hypothesis_transform, **kwargs
    )
    return measures["wil"]


def compute_measures(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform] = wer_default,
    **kwargs
) -> Dict[str, float]:
    """
    Calculate error measures between a set of ground-truth sentences and a set of
    hypothesis sentences.

    The set of sentences can be given as a string or a list of strings. A string
    input is assumed to be a single sentence. A list of strings is assumed to be
    multiple sentences which need to be evaluated independently. Each word in a
    sentence is separated by one or more spaces. A sentence is not expected to end
    with a specific token (such as a `.`). If the ASR system does delimit sentences
    it is expected that these tokens are filtered out.

    The optional `transforms` arguments can be used to apply pre-processing to
    respectively the ground truth and hypotheses input. By default, the following
    transform is applied to both the ground truth and hypothesis string(s). These
    steps are required and necessary in order to compute the measures.

    1) The start and end of a string are stripped of white-space symbols
    2) Contiguous spaces (e.g `   `) are reduced to a single space (e.g ` `)
    3) A sentence (with a single space (` `) between words) is reduced to a
       list of words

    Any non-default transformation is required to reduce the input to at least
    one list of words in order to facility the computation of the edit distance.

    :param truth: the ground-truth sentence(s) as a string or list of strings
    :param hypothesis: the hypothesis sentence(s) as a string or list of strings
    :param truth_transform: the transformation to apply on the truths input
    :param hypothesis_transform: the transformation to apply on the hypothesis input
    :return: a dict with WER, MER, WIP and WIL measures as floating point numbers
    """
    # deprecated old API
    if "standardize" in kwargs:
        warnings.warn(
            UserWarning(
                "keyword argument `standardize` is deprecated. "
                "Please use `truth_transform=jiwer.transformations.wer_standardize` and"
                " `hypothesis_transform=jiwer.transformations.wer_standardize` instead"
            )
        )
        truth_transform = wer_standardize
        hypothesis_transform = wer_standardize
    if "words_to_filter" in kwargs:
        warnings.warn(
            UserWarning(
                "keyword argument `words_to_filter` is deprecated. "
                "Please compose your own transform with `jiwer.transforms.RemoveSpecificWords"
            )
        )
        t = tr.RemoveSpecificWords(kwargs["words_to_filter"])
        truth = t(truth)
        hypothesis = t(hypothesis)

    # validate input type
    if isinstance(truth, str):
        truth = [truth]
    if isinstance(hypothesis, str):
        hypothesis = [hypothesis]
    if any(len(t) == 0 for t in truth):
        raise ValueError("one or more groundtruths are empty strings")

    # Preprocess truth and hypothesis
    truth, hypothesis = _preprocess(
        truth, hypothesis, truth_transform, hypothesis_transform
    )
    words_alignment.set_truth_hypothesis(truth, hypothesis)

    # keep track of total hits, substitutions, deletions and insertions
    # across all input sentences
    H, S, D, I = 0, 0, 0, 0

    # also keep track of the total number of ground truth words and hypothesis words
    gt_tokens, hp_tokens = 0, 0

    for groundtruth_sentence, hypothesis_sentence in zip(truth, hypothesis):
        # Get the operation counts (#hits, #substitutions, #deletions, #insertions)
        hits, substitutions, deletions, insertions = _get_operation_counts(
            groundtruth_sentence, hypothesis_sentence
        )

        H += hits
        S += substitutions
        D += deletions
        I += insertions
        gt_tokens += len(groundtruth_sentence)
        hp_tokens += len(hypothesis_sentence)

    # Compute Word Error Rate
    wer = float(S + D + I) / float(H + S + D)

    # Compute Match Error Rate
    mer = float(S + D + I) / float(H + S + D + I)

    # Compute Word Information Preserved
    wip = (float(H) / gt_tokens) * (float(H) / hp_tokens) if hp_tokens >= 1 else 0

    # Compute Word Information Lost
    wil = 1 - wip

    return {
        "wer": wer,
        "mer": mer,
        "wil": wil,
        "wip": wip,
        "hits": H,
        "substitutions": S,
        "deletions": D,
        "insertions": I,
    }


################################################################################
# Implementation of character error rate


def cer(
    truth: Union[str, List[str]],
    hypothesis: Union[str, List[str]],
    truth_transform: Union[tr.Compose, tr.AbstractTransform] = cer_default_transform,
    hypothesis_transform: Union[
        tr.Compose, tr.AbstractTransform
    ] = cer_default_transform,
    return_dict: bool = False,
) -> Union[float, Dict[str, Union[float, int]]]:
    """
    Calculate character error rate (CER) between a set of ground-truth sentences and
    a set of hypothesis sentences. By default, the CER includes space (` `) as a
    character over which the error rate is computed.

    :param truth: the ground-truth sentence(s) as a string or list of strings
    :param hypothesis: the hypothesis sentence(s) as a string or list of strings
    :param truth_transform: the transformation to apply on the truths input
    :param hypothesis_transform: the transformation to apply on the hypothesis input
    :param return_dict: when true, return a dictionary containing the CER and the number of
    insertions, deletions, substitution and hits between truth and hypothesis. When false,
    only return the CER as a floating point number
    :return: CER as a floating point number, or dictionary containing CER, #hits, #substitutions, #deletions and #insertions
    """
    r = compute_measures(truth, hypothesis, truth_transform, hypothesis_transform)

    result_dict = {
        "cer": r["wer"],
        "hits": r["hits"],
        "substitutions": r["substitutions"],
        "deletions": r["deletions"],
        "insertions": r["insertions"],
    }

    if return_dict:
        return result_dict
    else:
        return result_dict["cer"]


################################################################################
# Implementation of helper methods


def _preprocess(
    truth: List[str],
    hypothesis: List[str],
    truth_transform: Union[tr.Compose, tr.AbstractTransform],
    hypothesis_transform: Union[tr.Compose, tr.AbstractTransform],
) -> Tuple[List[str], List[str]]:
    """
    Pre-process the truth and hypothesis into a form such that the Levenshtein
    library can compute the edit operations.can handle.

    :param truth: the ground-truth sentence(s) as a string or list of strings
    :param hypothesis: the hypothesis sentence(s) as a string or list of strings
    :param truth_transform: the transformation to apply on the truths input
    :param hypothesis_transform: the transformation to apply on the hypothesis input
    :return: the preprocessed truth and hypothesis
    """
    # Apply transforms. The transforms should collapses input to a list of list of words
    transformed_truth = truth_transform(truth)
    transformed_hypothesis = hypothesis_transform(hypothesis)

    # raise an error if the ground truth is empty or the output
    # is not a list of list of strings
    if len(transformed_truth) != len(transformed_hypothesis):
        raise ValueError(
            "number of ground truth inputs ({}) and hypothesis inputs ({}) must match.".format(
                len(transformed_truth), len(transformed_hypothesis)
            )
        )
    if not _is_list_of_list_of_strings(transformed_truth, require_non_empty_lists=True):
        raise ValueError(
            "truth should be a list of list of strings after transform which are non-empty"
        )
    if not _is_list_of_list_of_strings(
        transformed_hypothesis, require_non_empty_lists=False
    ):
        raise ValueError(
            "hypothesis should be a list of list of strings after transform"
        )

    # tokenize each word into an integer
    vocabulary = set(chain(*transformed_truth, *transformed_hypothesis))
    words_alignment.set_vocabulary(vocabulary)

    if "" in vocabulary:
        raise ValueError(
            "Empty strings cannot be a word. "
            "Please ensure that the given transform removes empty strings."
        )

    word2char = dict(zip(vocabulary, range(len(vocabulary))))
    words_alignment.set_word2char(word2char)

    truth_chars = [
        "".join([chr(word2char[w]) for w in sentence]) for sentence in transformed_truth
    ]
    hypothesis_chars = [
        "".join([chr(word2char[w]) for w in sentence])
        for sentence in transformed_hypothesis
    ]

    return truth_chars, hypothesis_chars


def _is_list_of_list_of_strings(x: Any, require_non_empty_lists: bool):
    if not isinstance(x, list):
        return False

    for e in x:
        if not isinstance(e, list):
            return False

        if require_non_empty_lists and len(e) == 0:
            return False

        if not all([isinstance(s, str) for s in e]):
            return False

    return True


def _get_operation_counts(
    source_string: str, destination_string: str
) -> Tuple[int, int, int, int]:
    """
    Check how many edit operations (delete, insert, replace) are required to
    transform the source string into the destination string. The number of hits
    can be given by subtracting the number of deletes and substitutions from the
    total length of the source string.

    :param source_string: the source string to transform into the destination string
    :param destination_string: the destination to transform the source string into
    :return: a tuple of #hits, #substitutions, #deletions, #insertions
    """
    editops = Levenshtein.editops(source_string, destination_string)
    words_alignment.add_editops(editops)

    substitutions = sum(1 if op[0] == "replace" else 0 for op in editops)
    deletions = sum(1 if op[0] == "delete" else 0 for op in editops)
    insertions = sum(1 if op[0] == "insert" else 0 for op in editops)
    hits = len(source_string) - (substitutions + deletions)

    return hits, substitutions, deletions, insertions
