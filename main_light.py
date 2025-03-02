import re
from flask import Flask, request, jsonify
import json
from flask_sqlalchemy import SQLAlchemy
from collections import OrderedDict

app = Flask(__name__)

# SQLiteを利用する設定
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory_system.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 在庫モデルの定義（collationオプションを削除）
class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(8), nullable=False)  # 大文字と小文字を区別する必要がある場合は、SQLiteでは別途対応が必要です
    amount = db.Column(db.Integer, nullable=False)

# 売上モデルの定義
class Sales(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)  # 外部キーでItemテーブルと紐付け
    sales = db.Column(db.Float, nullable=False)
    
    item = db.relationship('Item', backref=db.backref('sales', lazy=True))  # リレーションシップの定義

# データベースのテーブル作成
with app.app_context():
    db.create_all()

# アイテムの追加エンドポイント
@app.route('/v1/stocks', methods=['POST'])
def add_item():
    data = request.get_json()
    name = data['name']
    amount = data.get('amount', 1)  # デフォルトの値を1

    # nameはアルファベットの大文字小文字のみを許可し、8文字以内であることを確認
    if not re.match("^[a-zA-Z]{1,8}$", name):
        return jsonify({"message": "ERROR"}), 400

    # amountが整数でなければエラーメッセージを返す
    if not isinstance(amount, int):
        return jsonify({"message": "ERROR"}), 400

    # 同じitemが存在するか確認
    existing_item = Item.query.filter_by(name=name).first()
    
    if existing_item:  # 同じitemがある場合
        existing_item.amount += amount
    else:  # 同じitemがない場合
        new_item = Item(name=name, amount=amount)
        db.session.add(new_item)

    db.session.commit()
    return jsonify({"name": name, "amount": amount}), 201 

# 特定アイテムの取得エンドポイント
@app.route('/v1/stocks/<name>', methods=['GET'])
def get_item(name):
    item = Item.query.filter_by(name=name).first()
    if item:  # 存在する場合
        return jsonify({name: item.amount})
    else:
        return jsonify({name: 0})

# 全アイテムの在庫取得エンドポイント
@app.route('/v1/stocks', methods=['GET'])
def get_all_items():
    items = Item.query.all()
    result = {item.name: item.amount for item in items}
    return jsonify(result)

# 販売のエンドポイント
@app.route('/v1/sales', methods=['POST'])
def sale_item():
    data = request.get_json()
    name = data['name']
    amount = data.get('amount', 1)  # デフォルトの値を1

    # amountが整数でなければエラーメッセージを返す
    if not isinstance(amount, int):
        return jsonify({"message": "ERROR"}), 400

    # 在庫に指定されたitemデータが存在するか確認
    existing_item = Item.query.filter_by(name=name).first()

    # priceが指定されなかったときの処理
    if 'price' not in data:
        if existing_item and existing_item.amount >= amount:
            existing_item.amount -= amount
        else:
            return jsonify("Not enough stock available"), 400
        db.session.commit()
        return jsonify({"name": name, "amount": amount}), 201

    price = data['price']

    if existing_item:
        if price > 0:
            if existing_item.amount >= amount:
                existing_item.amount -= amount
            else:
                return jsonify("Not enough stock available"), 400

            existing_sales = Sales.query.filter_by(item_id=existing_item.id).first()
            if existing_sales:
                existing_sales.sales += price * amount
            else:
                new_sales = Sales(item_id=existing_item.id, sales=price * amount)
                db.session.add(new_sales)

            db.session.commit()
            return jsonify({"name": name, "amount": amount, "price": price}), 201
        else:
            return jsonify("Invalid price"), 400
    else:
        return jsonify("Item not found"), 404

# 全体の売上表示エンドポイント
@app.route('/v1/sales', methods=['GET'])
def get_total_sales():
    total_sales = db.session.query(db.func.sum(Sales.sales)).scalar()
    if total_sales is None:
        total_sales = 0
    return jsonify({"sales": total_sales})

# 全削除するエンドポイント
@app.route('/v1/stocks', methods=['DELETE'])
def delete_all_records():
    db.session.query(Sales).delete()
    db.session.query(Item).delete()
    db.session.commit()
    return ''

# アイテムごとの売上取得エンドポイント
@app.route('/v1/sales/<name>', methods=['GET'])
def get_sales(name):
    record = db.session.query(Sales).join(Item).filter(Item.name == name).first()
    if record:
        return jsonify({name: record.sales})
    else:
        return jsonify({name: 0})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
