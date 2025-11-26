from rest_framework import serializers

class ForecastPointSerializer(serializers.Serializer):
    date = serializers.DateField()
    predicted = serializers.FloatField()
    actual = serializers.FloatField(required=False, allow_null=True)
    product_id = serializers.IntegerField(required=False, allow_null=True)
    product_name = serializers.CharField(required=False, allow_blank=True)


class RestockRecommendationSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    product_name = serializers.CharField()
    sku = serializers.CharField(required=False, allow_blank=True)
    current_stock = serializers.IntegerField()
    avg_daily_sales = serializers.FloatField()
    suggested_restock = serializers.IntegerField()


class ForecastResponseSerializer(serializers.Serializer):
    view = serializers.CharField(default='daily')
    horizon = serializers.IntegerField()
    historical = ForecastPointSerializer(many=True)
    forecast = ForecastPointSerializer(many=True)
    restock_recommendations = serializers.DictField(required=False, allow_null=True)
    meta = serializers.DictField()