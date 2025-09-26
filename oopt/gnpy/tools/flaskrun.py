from flask import Flask, request, jsonify
from cli_examples import transmission_main_example
from gnpy.tools.tranmission_test import transmission_main_example2

app = Flask(__name__)


@app.route('/run', methods=['POST'])
def run_script():
    # 接收 JSON 参数（示例）
    data = request.get_json()
    param1 = data.get('param1')

    # 调用指定函数（例如处理 JSON 文件）
    result = process_file(param1)

    # 返回响应
    return jsonify({"status": "success", "result": result})


@app.route('/hello', methods=['GET'])
def hello_word():
    print("hello_word")
    transmission_main_example2()
    result = 0
    return jsonify({"status": "success", "result": result})


def process_file(param):
    # 自定义业务逻辑（如读取/处理 JSON 文件）
    return f"Processed: {param}"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=32777)  # 绑定到所有网络接口，并指定端口