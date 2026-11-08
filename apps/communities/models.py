from django.conf import settings
from django.db import models
from django.utils.text import slugify

from apps.common.models import TimeStampedModel


class Community(TimeStampedModel):
    """A scientific community centered on a discipline, problem, or institution."""

    class Category(models.TextChoices):
        DISCIPLINE = "discipline", "Discipline"
        PROBLEM = "problem", "Problem area"
        INSTITUTION = "institution", "Institution"
        OTHER = "other", "Other"

    class Visibility(models.TextChoices):
        PUBLIC = "public", "Public"
        RESTRICTED = "restricted", "Restricted"
        PRIVATE = "private", "Private"

    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True, blank=True)
    description = models.TextField(max_length=2000)
    purpose = models.CharField(
        max_length=200,
        blank=True,
        help_text="A short statement of what this community works on.",
    )
    category = models.CharField(
        max_length=20,
        choices=Category.choices,
        default=Category.DISCIPLINE,
    )
    visibility = models.CharField(
        max_length=20,
        choices=Visibility.choices,
        default=Visibility.PUBLIC,
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_communities",
    )
    members = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        through="CommunityMembership",
        related_name="communities",
        blank=True,
    )

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "communities"

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name)[:120] or "community"
            slug = base
            counter = 2
            while Community.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class CommunityMembership(TimeStampedModel):
    """Connects a user to a community with a role and an approval status."""

    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MODERATOR = "moderator", "Moderator"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PENDING = "pending", "Pending"
        REJECTED = "rejected", "Rejected"

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    joined_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("community", "user")]
        ordering = ["role", "joined_at", "id"]

    def __str__(self):
        return f"{self.user} · {self.community} ({self.status})"

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def can_manage(self):
        return (
            self.is_active
            and self.role in {self.Role.OWNER, self.Role.MODERATOR}
        )
