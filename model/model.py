import tensorflow as tf
import tensorflow.contrib.layers as tfcl
from tensorflow.contrib.rnn import GRUCell
import tensorflow.contrib.legacy_seq2seq as seq2seq
import math
import sys
sys.path.append("..")
# import model.value
# import model.policy

def fc(inputs, num_nodes, name='0', activation=tf.nn.relu):
    weights = tf.get_variable('W_' + name,
                              shape=(inputs.shape[1], num_nodes),
                              dtype=tf.float32,
                              initializer=tfcl.variance_scaling_initializer())

    bias = tf.get_variable('b_' + name,
                           shape=[num_nodes],
                           dtype=tf.float32,
                           initializer=tfcl.variance_scaling_initializer())

    net_value = tf.matmul(inputs, weights) + bias
    return activation(net_value)

def get_gru(num_layers, state_dim, reuse=False):
    with tf.variable_scope('gru', reuse=reuse):
        gru_cells = []
        for _ in range(num_layers):
            gru_cells.append(GRUCell(state_dim))

    return gru_cells


class Model:
    def __init__(self, input_size=10, num_layers=1, layer_size=256, trainable = True, discount = .9, naive=False):
        self.input_size = input_size
        self.num_layers = num_layers
        self.layer_size = layer_size
        self.inputs_ph = None
        self.targets_ph = None # useless for 'real' model, just here for the proof of concept
        self.actions_op = None
        self.value_op = None
        self.loss_op = None
        self.optimizer = None
        self.saver = None
        self.trainable = trainable
        self.graph = tf.Graph()
        self.discount = discount
        self.entropy_weight = 1e-4
        self.naive = naive
        self.build_network()


    def get_params(self):
        return {"input_size":self.input_size, "layer_size":self.layer_size, "trainable": self.trainable, "discount":self.discount}

    def build_network(self):
        with self.graph.as_default():
            self.inputs_ph = tf.placeholder(tf.float32, shape=[1, self.input_size], name='inputs')
            self.targets_ph = tf.placeholder(tf.float32, shape=[1], name='targets')

            inputs = tf.split(self.inputs_ph, self.input_size, axis=1)

            if self.naive:
                network = fc(self.inputs_ph, self.layer_size)
            else:
                gru_cells = get_gru(self.num_layers, self.layer_size)
                multi_cell = tf.nn.rnn_cell.MultiRNNCell(gru_cells)
                initial_state = multi_cell.zero_state(batch_size=1, dtype=tf.float32)

                with tf.variable_scope('rnn_decoder') as scope:
                    outputs, final_state = seq2seq.rnn_decoder(inputs, initial_state, multi_cell)

                network = final_state

            # Approach for a discrete action space, where we can either
            # buy or sell but don't specify an amount
            # logits = fc(output, 2, name='logits')
            # actions = tf.nn.softmax(logits)

            # Approach for a continuous space.
            # 'Action' is a real number in [-1,1], where
            # -1 means 'sell everything you have',
            # 0 means 'do nothing', and
            # 1 means 'buy everything you can'.
            # Exchange should know how to interpret this number.
            self.actions_op = fc(network[0], 1, name='action', activation=tf.nn.tanh)
            self.value_op = fc(network[0], 1, name='v')
            self.loss_op = tf.reduce_sum(self.targets_ph - self.actions_op, axis=1)
            self.optimizer = tf.train.RMSPropOptimizer(0.01).minimize(self.loss_op)

            #with tf.Session(graph=self.graph) as sess:
            #    sess.run(tf.global_variables_initializer())

            self.saver = tf.train.Saver()

    def update_policy(R, rewards, actions):

        self.entropy = tf.reduce_sum(-1/2 * (tf.log(2*self.action * self.sd ** 2) + 1), 1, name="entropy") # if multiple dimensions, reduce to one

        self.losses = - (tf.log(actions) * self.targets + self.entropy_weight * self.entropy)
        self.loss = tf.reduce_sum(self.losses, name="loss")

        #self.optimizer = tf.train.AdamOptimizer(1e-4)
        self.optimizer = tf.train.RMSPropOptimizer(0.00025, 0.99, 0.0, 1e-6)
        self.grads_and_vars = self.optimizer.compute_gradients(self.loss)
        self.grads_and_vars = [[grad, var] for grad, var in self.grads_and_vars if grad is not None]
        self.train_op = self.optimizer.apply_gradients(self.grads_and_vars, global_step=tf.contrib.framework.get_global_step())

    def get_state(self):
        # needs to return Cell Vector, Hidden Vector
        return 0

    def get_both(self, sess, input):
        #session.run(self.global_model.actions_op, feed_dict={self.global_model.inputs_ph: hp_reshaped})
        with tf.Session() as sess:
            value, action = sess.run([self.value_op, self.action_op], feed_dict={self.input_ph: input})
        return value, action


    def get_value(self, sess, input):
        #session.run(self.global_model.actions_op, feed_dict={self.global_model.inputs_ph: hp_reshaped})
        with tf.Session() as sess:
            value = sess.run(self.value_op, feed_dict={self.input_ph: input})
        return value

    def get_policy(self, sess, input):
        with tf.Session() as sess:
            policy = sess.run(self.policy_op, feed_dict={self.input_ph: input})
        return policy

