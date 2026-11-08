from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel


class FieldVisibility(models.TextChoices):
    PUBLIC = "public", "Anyone"
    AUTHENTICATED = "authenticated", "Signed-in people"
    PRIVATE = "private", "Only me"


def visibility_field(default):
    return models.CharField(
        max_length=20,
        choices=FieldVisibility.choices,
        default=default,
    )


class Tag(TimeStampedModel):
    """A shared label used for post tags, interests, and skills."""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=60, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class User(AbstractUser):
    """Platform user. Email is unique because it is an account identifier."""

    email = models.EmailField(unique=True)
    # New accounts must prove control of their email before they can publish
    # contributions or take part in discussions. Existing accounts are marked
    # verified by the accompanying data migration.
    email_verified = models.BooleanField(default=False)

    def __str__(self):
        return self.username


class Profile(TimeStampedModel):
    """Information a person chooses to show about their work and learning."""

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    bio = models.TextField(blank=True, max_length=1000)
    institution = models.CharField(max_length=200, blank=True)
    location = models.CharField(max_length=120, blank=True)
    interests = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="interested_profiles",
    )
    skills = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="skilled_profiles",
    )
    research_interests = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="research_profiles",
    )
    avatar_visibility = visibility_field(FieldVisibility.PUBLIC)
    bio_visibility = visibility_field(FieldVisibility.PUBLIC)
    institution_visibility = visibility_field(FieldVisibility.AUTHENTICATED)
    location_visibility = visibility_field(FieldVisibility.AUTHENTICATED)
    interests_visibility = visibility_field(FieldVisibility.PUBLIC)
    skills_visibility = visibility_field(FieldVisibility.PUBLIC)
    education_visibility = visibility_field(FieldVisibility.AUTHENTICATED)
    experience_visibility = visibility_field(FieldVisibility.AUTHENTICATED)
    languages_visibility = visibility_field(FieldVisibility.PUBLIC)
    research_interests_visibility = visibility_field(FieldVisibility.PUBLIC)
    achievements_visibility = visibility_field(FieldVisibility.PUBLIC)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}'s profile"


class Education(TimeStampedModel):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="education",
    )
    institution = models.CharField(max_length=200)
    qualification = models.CharField(max_length=200, blank=True)
    field_of_study = models.CharField(max_length=200, blank=True)
    start_year = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, max_length=1000)

    class Meta:
        ordering = ["-start_year", "id"]

    def __str__(self):
        return f"{self.qualification or 'Study'} · {self.institution}"


class ProfessionalExperience(TimeStampedModel):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="experience",
    )
    title = models.CharField(max_length=200)
    organization = models.CharField(max_length=200)
    start_year = models.PositiveIntegerField(null=True, blank=True)
    end_year = models.PositiveIntegerField(null=True, blank=True)
    description = models.TextField(blank=True, max_length=1000)

    class Meta:
        ordering = ["-start_year", "id"]

    def __str__(self):
        return f"{self.title} · {self.organization}"


class Language(TimeStampedModel):
    class Proficiency(models.TextChoices):
        BASIC = "basic", "Basic"
        CONVERSATIONAL = "conversational", "Conversational"
        PROFESSIONAL = "professional", "Professional"
        FLUENT = "fluent", "Fluent"
        NATIVE = "native", "Native"

    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="languages",
    )
    name = models.CharField(max_length=80)
    proficiency = models.CharField(
        max_length=20,
        choices=Proficiency.choices,
        blank=True,
    )

    class Meta:
        ordering = ["name", "id"]

    def __str__(self):
        return self.name


class Achievement(TimeStampedModel):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name="achievements",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, max_length=1000)
    year = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-year", "id"]

    def __str__(self):
        return self.title


class AuthToken(TimeStampedModel):
    """A single-use secret for email verification or password reset."""

    class Purpose(models.TextChoices):
        EMAIL_VERIFY = "email_verify", "Email verification"
        PASSWORD_RESET = "password_reset", "Password reset"

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="auth_tokens",
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "purpose"]),
        ]

    def __str__(self):
        return f"{self.purpose} for {self.user_id}"


class UserSession(TimeStampedModel):
    """A browser session the account holder can review and revoke."""

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tracked_sessions",
    )
    session_key = models.CharField(max_length=40, unique=True)
    user_agent = models.CharField(max_length=300, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_seen = models.DateTimeField()

    class Meta:
        ordering = ["-last_seen"]

    def __str__(self):
        return f"{self.user} · {self.session_key[:8]}"
