# Copyright 2015 Google Inc. All Rights Reserved.
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
# ==============================================================================

"""Tests for Debugger Session."""
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import threading
import time

import numpy as np
import six
from six.moves import xrange  # pylint: disable=redefined-builtin

from tensorflow.core.lib.core import error_codes_pb2
from tensorflow.core.protobuf import config_pb2
from tensorflow.python.client import debugger
from tensorflow.python.client import session
from tensorflow.python.framework import dtypes
from tensorflow.python.framework import errors
from tensorflow.python.framework import ops
from tensorflow.python.framework import tensor_util
from tensorflow.python.framework import test_util
from tensorflow.python.framework import versions
from tensorflow.python.ops import array_ops
from tensorflow.python.ops import constant_op
from tensorflow.python.ops import control_flow_ops
from tensorflow.python.ops import math_ops
from tensorflow.python.ops import state_ops
from tensorflow.python.ops import variables
from tensorflow.python.platform import googletest
from tensorflow.python.util import compat


# NOTE(mrry): Dummy shape registration for op used in the tests.
ops.RegisterShape('ConstructionFails')(None)


class DebugSessionTest(test_util.TensorFlowTestCase):

  def setUp(self):
    # TODO(cais): Proper mutex locking to push down to
    self._init_delay_sec = 0.1
    self._step_delay_sec = 0.02

  def _auto_step(self, debug_round):
    while True:
      debug_round.step()

      node_order = debug_round.query_node_order()
      node_idx = debug_round.where()
      is_complete = debug_round.is_complete()

      node_just_completed = node_order[node_idx]
      print("Node just completed: %s" % node_just_completed)

      if is_complete:
        debug_round.step()
        break

  def testPlaceHolderAddingSingleSteps(self):
    with session.Session("debug") as debug_sess:
      a = constant_op.constant(6.0, shape=[1, 1], name="a")
      b = constant_op.constant(7.0, shape=[1, 1], name="b")
      s = math_ops.add(a, b, name="s")

      # Create a DebugRound object
      debug_round = debugger.DebugRound(debug_sess, s)

      node_order = debug_round.query_node_order()
      self.assertTrue(isinstance(node_order, list))
      num_nodes = len(node_order)

      curr_pos = debug_round.where()
      self.assertEquals(0, curr_pos)

      while True:
        debug_round.step()

        # Verify that stepping causes the "where index" to increment properly
        node_idx = debug_round.where()
        self.assertEquals(curr_pos + 1, node_idx)
        curr_pos = node_idx

        # Verify is_complete
        is_complete = debug_round.is_complete()
        self.assertEquals(curr_pos == num_nodes - 1, is_complete)

        node_just_completed = node_order[node_idx]
        print("Node just completed: %s" % node_just_completed)

        if is_complete:
          debug_round.step()
          break

      debug_round.join()

  def testPlaceHolderAddingMultiSteps(self):
    with session.Session("debug") as debug_sess:
      a = constant_op.constant(6.0, shape=[1, 1], name="a")
      b = constant_op.constant(7.0, shape=[1, 1], name="b")
      s = math_ops.add(a, b, name="s")

      # Create a DebugRound object
      debug_round = debugger.DebugRound(debug_sess, s)

      node_order = debug_round.query_node_order()
      self.assertTrue(isinstance(node_order, list))
      num_nodes = len(node_order)

      curr_pos = debug_round.where()
      self.assertEquals(0, curr_pos)

      while True:
        debug_round.step(2)

        # Verify that stepping causes the "where index" to increment properly
        node_idx = debug_round.where()
        if curr_pos + 2 >= num_nodes:
          self.assertEquals(num_nodes - 1, node_idx)
        else:
          self.assertEquals(curr_pos + 2, node_idx)
        curr_pos = node_idx

        # Verify is_complete
        is_complete = debug_round.is_complete()
        self.assertEquals(curr_pos == num_nodes - 1, is_complete)

        node_just_completed = node_order[node_idx]
        print("Node just completed: %s" % node_just_completed)

        if is_complete:
          debug_round.step()
          break

      debug_round.join()

  def testPlaceHolderAddingContinue(self):
    with session.Session("debug") as debug_sess:
      a = constant_op.constant(6.0, shape=[1, 1], name="a")
      b = constant_op.constant(7.0, shape=[1, 1], name="b")
      s = math_ops.add(a, b, name="s")

      # Create a DebugRound object
      debug_round = debugger.DebugRound(debug_sess, s)

      node_order = debug_round.query_node_order()
      self.assertTrue(node_order.count("s") == 1)

      # Continue until node "s" has just finished executing
      debug_round.cont("s")

      # Verify that the debug breaks on "s"
      self.assertEquals(node_order.index("s"), debug_round.where())

      self._auto_step(debug_round)

  def testPlaceHolderAddingContinueToEnd(self):
    with session.Session("debug") as debug_sess:
      a = constant_op.constant(6.0, shape=[1, 1], name="a")
      b = constant_op.constant(7.0, shape=[1, 1], name="b")
      s = math_ops.add(a, b, name="s")

      # Create a DebugRound object
      debug_round = debugger.DebugRound(debug_sess, s)

      # Calling cont() without node_name specified should let the debug round
      # continue to the end
      debug_round.cont()

      # Verify that the debug breaks on the last node
      self.assertEquals(len(debug_round.query_node_order()) - 1,
                        debug_round.where())

      self._auto_step(debug_round)


if __name__ == '__main__':
  googletest.main()
