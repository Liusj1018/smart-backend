"""Generate a tiny ONNX model for demo / warm-up purposes.

Produces a simple Linear: Y = X @ W + B with input shape [1, 4] and output [1, 2].
This is only used so the CV service has a valid model to load at startup;
replace /app/model.onnx with a real trained model in production.
"""

import numpy as np
import onnx
from onnx import TensorProto, helper, numpy_helper

def main() -> None:
    input_shape = ["batch", 4]
    weight = np.array(
        [[0.1, 0.4], [0.2, 0.5], [0.3, 0.6], [0.7, 0.8]], dtype=np.float32
    )
    bias = np.array([0.1, -0.1], dtype=np.float32)

    X = helper.make_tensor_value_info("X", TensorProto.FLOAT, input_shape)
    Y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, ["batch", 2])

    W_init = numpy_helper.from_array(weight, name="W")
    B_init = numpy_helper.from_array(bias, name="B")

    matmul = helper.make_node("MatMul", ["X", "W"], ["XM"])
    add = helper.make_node("Add", ["XM", "B"], ["Y"])

    graph = helper.make_graph(
        [matmul, add],
        "tiny_linear",
        [X],
        [Y],
        initializer=[W_init, B_init],
    )
    model = helper.make_model(
        graph, opset_imports=[helper.make_opsetid("", 17)]
    )
    model.ir_version = 9  # compatible with onnxruntime 1.20
    onnx.checker.check_model(model)
    onnx.save(model, "/app/model.onnx")
    print("wrote /app/model.onnx")


if __name__ == "__main__":
    main()