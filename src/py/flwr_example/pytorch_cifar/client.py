# Copyright 2020 Adap GmbH. All Rights Reserved.
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
"""Flower client example using PyTorch for CIFAR-10 image classification."""


import argparse
import timeit

import torch
import torchvision

import flwr as fl
from flwr.common import EvaluateIns, EvaluateRes, FitIns, FitRes, ParametersRes, Weights

from . import DEFAULT_SERVER_ADDRESS, cifar

# pylint: disable=no-member
DEVICE = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
# pylint: enable=no-member


class CifarClient(fl.client.Client):
    """Flower client implementing CIFAR-10 image classification using PyTorch."""

    def __init__(
        self,
        model: cifar.Net,
        trainset: torchvision.datasets.CIFAR10,
        testset: torchvision.datasets.CIFAR10,
    ) -> None:
        self.model = model
        self.trainset = trainset
        self.testset = testset

    def get_parameters(self) -> ParametersRes:

        weights: Weights = self.model.get_weights()
        parameters = fl.common.weights_to_parameters(weights)
        return ParametersRes(parameters=parameters)

    def fit(self, ins: FitIns) -> FitRes:

        weights: Weights = fl.common.parameters_to_weights(ins.parameters)
        config = ins.config
        fit_begin = timeit.default_timer()

        # Get training config
        epochs = int(config["epochs"])
        batch_size = int(config["batch_size"])

        # Set model parameters
        self.model.set_weights(weights)

        # Train model
        trainloader = torch.utils.data.DataLoader(
            self.trainset, batch_size=batch_size, shuffle=True
        )
        cifar.train(self.model, trainloader, epochs=epochs, device=DEVICE)

        # Return the refined weights and the number of examples used for training
        weights_prime: Weights = self.model.get_weights()
        params_prime = fl.common.weights_to_parameters(weights_prime)
        num_examples_train = len(self.trainset)
        fit_duration = timeit.default_timer() - fit_begin
        return FitRes(
            parameters=params_prime,
            num_examples=num_examples_train,
            num_examples_ceil=num_examples_train,
            fit_duration=fit_duration,
        )

    def evaluate(self, ins: EvaluateIns) -> EvaluateRes:

        weights = fl.common.parameters_to_weights(ins.parameters)

        # Use provided weights to update the local model
        self.model.set_weights(weights)

        # Evaluate the updated model on the local dataset
        testloader = torch.utils.data.DataLoader(
            self.testset, batch_size=32, shuffle=False
        )
        loss, accuracy = cifar.test(self.model, testloader, device=DEVICE)

        # Return the number of evaluation examples and the evaluation result (loss)
        return EvaluateRes(
            loss=float(loss), num_examples=len(self.testset), accuracy=float(accuracy)
        )


def main() -> None:
    """Load data, create and start CifarClient."""

    # Load model and data
    model = cifar.load_model()
    model.to(DEVICE)
    trainset, testset = cifar.load_data()

    # Start client
    client = CifarClient(model, trainset, testset)
    fl.client.start_client("[::]:8060", client)


if __name__ == "__main__":
    main()
