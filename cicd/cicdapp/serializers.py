from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import serializers


User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="first_name")
    dob = serializers.DateField(source="profile.dob", allow_null=True)

    class Meta:
        model = User
        fields = ("name", "email", "dob")


class RegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    dob = serializers.DateField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate_email(self, value):
        email = value.strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError(
                "An account with this email already exists."
            )
        return email

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )

        temp_user = User(
            username=attrs["email"],
            email=attrs["email"],
            first_name=attrs["name"].strip(),
        )
        password_validation.validate_password(attrs["password"], user=temp_user)
        return attrs

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["email"],
            email=validated_data["email"],
            first_name=validated_data["name"].strip(),
            password=validated_data["password"],
        )
        user.profile.dob = validated_data["dob"]
        user.profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate(self, attrs):
        email = attrs["email"].strip().lower()
        password = attrs["password"]
        request = self.context.get("request")

        user = authenticate(request=request, username=email, password=password)
        if user is None:
            raise serializers.ValidationError(
                {"non_field_errors": ["Invalid email or password."]}
            )

        attrs["user"] = user
        attrs["email"] = email
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def save(self, **kwargs):
        request = self.context["request"]
        email = self.validated_data["email"].strip().lower()
        users = User.objects.filter(email__iexact=email, is_active=True)

        for user in users:
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            token = default_token_generator.make_token(user)
            reset_path = f"/password-reset/confirm/{uid}/{token}/"
            reset_link = request.build_absolute_uri(reset_path)
            send_mail(
                subject="Password reset for your Django Auth Practice account",
                message=(
                    "You're receiving this email because a password reset was "
                    "requested for your account.\n\n"
                    f"Follow this link to choose a new password:\n{reset_link}\n\n"
                    "If you didn't request a password reset, you can ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
            )


class PasswordResetConfirmSerializer(serializers.Serializer):
    new_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )
    confirm_password = serializers.CharField(
        write_only=True,
        style={"input_type": "password"},
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": ["Passwords do not match."]}
            )

        user = self.context["user"]
        password_validation.validate_password(attrs["new_password"], user=user)
        return attrs

    def save(self, **kwargs):
        user = self.context["user"]
        user.set_password(self.validated_data["new_password"])
        user.save(update_fields=["password"])
        return user


def get_user_from_reset_token(uidb64, token):
    try:
        user_id = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=user_id)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None

    if not default_token_generator.check_token(user, token):
        return None

    return user
