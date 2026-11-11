from datetime import timedelta

from django.contrib.auth.models import User
from django.db.models import Q
from django.test import override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.utils import timezone
from guardian.shortcuts import assign_perm, get_objects_for_user
from rest_framework import status
from rest_framework.test import APIClient

from app.models import Project, Task
from app.tests.classes import BootTestCase
from nodeodm import status_codes

QUEUED = status_codes.QUEUED
RUNNING = status_codes.RUNNING
FAILED = status_codes.FAILED
COMPLETED = status_codes.COMPLETED
CANCELED = status_codes.CANCELED

LIST_URL = "/api/projects/"


def days_ago(days):
    return timezone.now() - timedelta(days=days)


def make_task(project, status=None, partial=False, created_at=None, name="Task"):
    kwargs = {}
    if created_at is not None:
        kwargs['created_at'] = created_at
    return Task.objects.create(project=project, name=name, status=status, partial=partial, **kwargs)


def rows_of(res):
    """List responses are a plain array when no page is requested, paginated otherwise."""
    return res.data if isinstance(res.data, list) else res.data['results']


def ids_of(res):
    return [p['id'] for p in rows_of(res)]


class TestApiProjectListFilters(BootTestCase):
    def setUp(self):
        super().setUp()
        self.owner = User.objects.get(username="testuser")
        self.member = User.objects.get(username="testuser2")
        self.admin = User.objects.get(username="testsuperuser")
        self.stranger = User.objects.create_user(username="testuser3",
                                                 email="user3@test.com",
                                                 password="test1234")

    def client_for(self, user):
        # force_login: the password backend is not configured (Tapis-only auth), see memory note
        client = APIClient()
        client.force_login(user)
        return client

    def get_ids(self, client, query=""):
        res = client.get(LIST_URL + query)
        self.assertEqual(res.status_code, status.HTTP_200_OK, msg=query)
        return ids_of(res)

    def make_project(self, name, owner=None):
        return Project.objects.create(owner=owner or self.owner, name=name)

    # ------------------------------------------------------------------
    # Visibility
    # ------------------------------------------------------------------

    def test_visibility_matrix(self):
        owned_active = self.make_project("Owned active")
        make_task(owned_active, QUEUED)
        make_task(owned_active, RUNNING)

        shared_failed = self.make_project("Shared failed")
        make_task(shared_failed, FAILED)
        assign_perm("view_project", self.member, shared_failed)

        private_canceled = self.make_project("Private canceled")
        make_task(private_canceled, CANCELED)

        self.make_project("Owned empty")

        admin_project = self.make_project("Admin completed", owner=self.admin)
        make_task(admin_project, COMPLETED)

        filter_queries = [
            "",
            "?hide_empty=true",
            "?has_active_work=true",
            "?hide_empty=true&has_active_work=true",
            "?hide_empty=false&has_active_work=false",
        ]

        for user in [self.owner, self.member, self.stranger, self.admin]:
            client = self.client_for(user)
            # Ground truth from guardian, object-level only. Global permissions
            # (e.g. via the Default group) do not grant per-project visibility here.
            expected_visible = set(get_objects_for_user(user, "app.view_project",
                                                        accept_global_perms=False).values_list("id", flat=True))
            unfiltered = self.get_ids(client)

            self.assertEqual(set(unfiltered), expected_visible, msg=user.username)

            for query in filter_queries:
                filtered = self.get_ids(client, query)
                self.assertEqual(len(filtered), len(set(filtered)), msg=(user.username, query))
                self.assertTrue(set(filtered) <= set(unfiltered), msg=(user.username, query))
                self.assertTrue(set(filtered) <= expected_visible, msg=(user.username, query))

        # Explicit cases
        # Owner sees own active project; the filter keeps it
        self.assertIn(owned_active.id, self.get_ids(self.client_for(self.owner), "?has_active_work=true"))

        # Member sees only the project shared with them, and the active-work filter keeps it
        member_client = self.client_for(self.member)
        member_active = self.get_ids(member_client, "?has_active_work=true")
        self.assertEqual(member_active, [shared_failed.id])
        self.assertNotIn(owned_active.id, self.get_ids(member_client))
        self.assertNotIn(private_canceled.id, self.get_ids(member_client))
        self.assertNotIn(admin_project.id, self.get_ids(member_client))

        # Non-member sees none of the owner's or admin's projects, with or without filters
        stranger_client = self.client_for(self.stranger)
        for query in filter_queries:
            self.assertEqual(self.get_ids(stranger_client, query), [], msg=query)

        # Admin sees everything
        admin_all = set(self.get_ids(self.client_for(self.admin)))
        self.assertTrue({owned_active.id, shared_failed.id, private_canceled.id, admin_project.id} <= admin_all)

        # Anonymous: no project is public here, so either the request is rejected
        # or it returns nothing (for every filter combination)
        anon = APIClient()
        for query in filter_queries:
            res = anon.get(LIST_URL + query)
            if res.status_code == status.HTTP_200_OK:
                self.assertEqual(ids_of(res), [], msg=query)
            else:
                self.assertIn(res.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN), msg=query)

    # ------------------------------------------------------------------
    # Empty / active definitions (spec section 3)
    # ------------------------------------------------------------------

    def test_empty_and_active_definitions(self):
        p = {}
        p['empty'] = self.make_project("Def empty")
        p['canceled'] = self.make_project("Def canceled")
        make_task(p['canceled'], CANCELED)
        p['completed'] = self.make_project("Def completed")
        make_task(p['completed'], COMPLETED)
        p['partial_null'] = self.make_project("Def partial null")
        make_task(p['partial_null'], None, partial=True)
        p['null_queued'] = self.make_project("Def null queued")
        make_task(p['null_queued'], None, partial=False)
        p['queued'] = self.make_project("Def queued")
        make_task(p['queued'], QUEUED)
        p['running'] = self.make_project("Def running")
        make_task(p['running'], RUNNING)
        p['failed_recent'] = self.make_project("Def failed recent")
        make_task(p['failed_recent'], FAILED, created_at=days_ago(1))
        p['failed_old'] = self.make_project("Def failed old")
        make_task(p['failed_old'], FAILED, created_at=days_ago(30))

        seeded_empty = Project.objects.get(name="User Test Project").id
        client = self.client_for(self.owner)

        all_ids = set(self.get_ids(client))
        for key, project in p.items():
            self.assertIn(project.id, all_ids, msg=key)

        not_empty = set(self.get_ids(client, "?hide_empty=true"))
        self.assertNotIn(p['empty'].id, not_empty)
        self.assertNotIn(seeded_empty, not_empty)
        for key in ['canceled', 'completed', 'partial_null', 'null_queued', 'queued', 'running',
                    'failed_recent', 'failed_old']:
            self.assertIn(p[key].id, not_empty, msg=key)

        active = set(self.get_ids(client, "?has_active_work=true"))
        self.assertEqual(active, {p['null_queued'].id, p['queued'].id, p['running'].id, p['failed_recent'].id})

        both = set(self.get_ids(client, "?hide_empty=true&has_active_work=true"))
        self.assertEqual(both, active)

        # Per-row counts agree with the definitions
        rows = {r['id']: r for r in rows_of(client.get(LIST_URL + "?hide_empty=false"))}
        self.assertEqual(rows[p['partial_null'].id]['task_counts'],
                         {'total': 1, 'queued': 0, 'running': 0, 'failed': 0})
        self.assertEqual(rows[p['null_queued'].id]['task_counts'],
                         {'total': 1, 'queued': 1, 'running': 0, 'failed': 0})
        self.assertEqual(rows[p['failed_old'].id]['task_counts'],
                         {'total': 1, 'queued': 0, 'running': 0, 'failed': 0})
        self.assertEqual(rows[p['failed_recent'].id]['task_counts'],
                         {'total': 1, 'queued': 0, 'running': 0, 'failed': 1})
        self.assertEqual(rows[p['canceled'].id]['task_counts'],
                         {'total': 1, 'queued': 0, 'running': 0, 'failed': 0})
        self.assertEqual(rows[p['empty'].id]['task_counts'],
                         {'total': 0, 'queued': 0, 'running': 0, 'failed': 0})

    @override_settings(PROJECT_LIST_FAILED_WINDOW_DAYS=7)
    def test_failed_window_boundary(self):
        inside = self.make_project("Inside window")
        make_task(inside, FAILED, created_at=timezone.now() - timedelta(days=7) + timedelta(hours=1))
        outside = self.make_project("Outside window")
        make_task(outside, FAILED, created_at=timezone.now() - timedelta(days=7) - timedelta(hours=1))

        client = self.client_for(self.owner)
        active = set(self.get_ids(client, "?has_active_work=true"))
        self.assertIn(inside.id, active)
        self.assertNotIn(outside.id, active)

        rows = {r['id']: r for r in rows_of(client.get(LIST_URL + "?page=1&page_size=20"))}
        self.assertEqual(rows[inside.id]['task_counts']['failed'], 1)
        self.assertEqual(rows[outside.id]['task_counts'], {'total': 1, 'queued': 0, 'running': 0, 'failed': 0})

    def test_failed_window_setting_is_read(self):
        project = self.make_project("Two days old failure")
        make_task(project, FAILED, created_at=days_ago(2))
        client = self.client_for(self.owner)

        with override_settings(PROJECT_LIST_FAILED_WINDOW_DAYS=1):
            self.assertNotIn(project.id, self.get_ids(client, "?has_active_work=true"))
        with override_settings(PROJECT_LIST_FAILED_WINDOW_DAYS=7):
            self.assertIn(project.id, self.get_ids(client, "?has_active_work=true"))

    # ------------------------------------------------------------------
    # Counts vs ORM, search interaction (no fan-out)
    # ------------------------------------------------------------------

    def orm_counts(self, project):
        window_start = timezone.now() - timedelta(days=7)
        tasks = Task.objects.filter(project=project)
        return {
            'total': tasks.count(),
            'queued': tasks.filter(Q(status=QUEUED) | Q(status__isnull=True, partial=False)).count(),
            'running': tasks.filter(status=RUNNING).count(),
            'failed': tasks.filter(status=FAILED, created_at__gte=window_start).count(),
        }

    def build_alpha_fixture(self):
        alpha = self.make_project("Alpha survey")
        for _ in range(2):
            make_task(alpha, QUEUED, name="alpha")
        make_task(alpha, RUNNING, name="alpha")
        for _ in range(2):
            make_task(alpha, FAILED, created_at=days_ago(1), name="alpha")
        make_task(alpha, FAILED, created_at=days_ago(30), name="alpha")
        make_task(alpha, COMPLETED, name="alpha")
        make_task(alpha, CANCELED, name="alpha")
        make_task(alpha, None, partial=True, name="alpha")
        make_task(alpha, None, partial=False, name="alpha")

        beta = self.make_project("Alpha beta")
        for _ in range(3):
            make_task(beta, RUNNING, name="alpha pass")

        empty = self.make_project("Alpha empty")
        completed_only = self.make_project("Alpha completed only")
        make_task(completed_only, COMPLETED, name="alpha")

        gamma = self.make_project("Gamma running")
        make_task(gamma, RUNNING, name="gamma")

        return {'alpha': alpha, 'beta': beta, 'empty': empty,
                'completed_only': completed_only, 'gamma': gamma}

    def test_counts_match_orm(self):
        projects = self.build_alpha_fixture()
        client = self.client_for(self.owner)

        for query in ["?page=1&page_size=20", "?page=1&page_size=20&search=alpha"]:
            res = client.get(LIST_URL + query)
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            rows = rows_of(res)
            ids = [r['id'] for r in rows]
            self.assertEqual(len(ids), len(set(ids)), msg=("duplicates", query))

            for row in rows:
                project = Project.objects.get(pk=row['id'])
                self.assertEqual(row['task_counts'], self.orm_counts(project), msg=(project.name, query))

        # The search-matched "Alpha survey" appears once, with its exact counts
        search_rows = {r['id']: r for r in rows_of(client.get(LIST_URL + "?page=1&page_size=20&search=alpha"))}
        self.assertEqual(search_rows[projects['alpha'].id]['task_counts'],
                         {'total': 10, 'queued': 3, 'running': 1, 'failed': 2})
        self.assertEqual(search_rows[projects['beta'].id]['task_counts'],
                         {'total': 3, 'queued': 0, 'running': 3, 'failed': 0})

    def test_search_intersection(self):
        projects = self.build_alpha_fixture()
        client = self.client_for(self.owner)

        self.assertEqual(
            set(self.get_ids(client, "?search=alpha")),
            {projects['alpha'].id, projects['beta'].id, projects['empty'].id, projects['completed_only'].id})

        intersect = client.get(LIST_URL + "?page=1&page_size=20&search=alpha&hide_empty=true&has_active_work=true")
        self.assertEqual(intersect.status_code, status.HTTP_200_OK)
        ids = ids_of(intersect)
        self.assertEqual(sorted(ids), sorted([projects['alpha'].id, projects['beta'].id]))
        self.assertEqual(len(ids), len(set(ids)))

        rows = {r['id']: r for r in rows_of(intersect)}
        self.assertEqual(rows[projects['alpha'].id]['task_counts']['total'], 10)
        self.assertEqual(rows[projects['beta'].id]['task_counts']['running'], 3)

    # ------------------------------------------------------------------
    # Pagination
    # ------------------------------------------------------------------

    def build_pagination_fixture(self):
        for i in range(25):
            project = self.make_project("Bulk %02d" % i)
            if i % 5 == 0:
                make_task(project, QUEUED)
            elif i in (1, 2):
                make_task(project, COMPLETED)
        # Owner visible total: 25 bulk projects + "User Test Project" (empty) = 26
        # hide_empty=true: 5 active + 2 completed = 7
        # has_active_work=true: 5

    def test_pagination(self):
        self.build_pagination_fixture()
        client = self.client_for(self.owner)

        # No page: plain array, unpaginated (MoveTaskDialog case)
        res = client.get(LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIsInstance(res.data, list)
        self.assertEqual(len(res.data), 26)

        # page without page_size: 10 per page
        res = client.get(LIST_URL + "?page=1")
        self.assertEqual(len(res.data['results']), 10)
        self.assertEqual(res.data['count'], 26)
        self.assertIsNotNone(res.data['next'])

        # page_size=20
        res = client.get(LIST_URL + "?page=1&page_size=20")
        self.assertEqual(len(res.data['results']), 20)
        self.assertEqual(res.data['count'], 26)

        res = client.get(LIST_URL + "?page=2&page_size=20")
        self.assertEqual(len(res.data['results']), 6)

        # master's ProjectsPagination: page_size is echoed and clamped to its max (100)
        self.assertEqual(res.data['page_size'], 20)
        res = client.get(LIST_URL + "?page=1&page_size=500")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['page_size'], 100)
        self.assertEqual(len(res.data['results']), 26)

        # count reflects the filtered total, not the page
        res = client.get(LIST_URL + "?page=1&page_size=20&hide_empty=true")
        self.assertEqual(res.data['count'], 7)
        self.assertEqual(len(res.data['results']), 7)

        res = client.get(LIST_URL + "?page=1&page_size=20&has_active_work=true")
        self.assertEqual(res.data['count'], 5)

        res = client.get(LIST_URL + "?page=1&page_size=20&hide_empty=true&has_active_work=true")
        self.assertEqual(res.data['count'], 5)

        # Paging through the filtered set returns every project exactly once
        expected = set(self.get_ids(client, "?hide_empty=true"))
        self.assertEqual(len(expected), 7)
        seen = []
        for page in (1, 2):
            res = client.get(LIST_URL + "?page=%d&page_size=5&hide_empty=true" % page)
            seen += ids_of(res)
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(set(seen), expected)

    # ------------------------------------------------------------------
    # Query count: task counts add no per-row SQL against app_task
    # ------------------------------------------------------------------

    def app_task_queries(self, client, query):
        with CaptureQueriesContext(connection) as ctx:
            res = client.get(LIST_URL + query)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        task_sql = [q['sql'] for q in ctx.captured_queries if 'app_task' in q['sql']]
        return len(task_sql), len(ctx.captured_queries)

    def add_query_count_projects(self, user, n, start):
        for i in range(start, start + n):
            project = Project.objects.create(owner=user, name="QC %02d" % i)
            make_task(project, QUEUED)
            make_task(project, FAILED, created_at=days_ago(1))

    def test_query_count_does_not_grow_with_rows(self):
        user = User.objects.create_user(username="qcuser", email="qc@test.com", password="test1234")
        client = self.client_for(user)

        self.add_query_count_projects(user, 2, 0)
        small_task_queries, small_total = self.app_task_queries(client, "?page=1&page_size=20")
        self.assertEqual(len(rows_of(client.get(LIST_URL + "?page=1&page_size=20"))), 2)

        self.add_query_count_projects(user, 18, 2)
        large_task_queries, large_total = self.app_task_queries(client, "?page=1&page_size=20")
        self.assertEqual(len(rows_of(client.get(LIST_URL + "?page=1&page_size=20"))), 20)

        self.assertEqual(small_task_queries, large_task_queries)

        # Baseline for the report (not a pass/fail): total SQL statements for 2 vs 20 rows
        print("\n[query-count baseline] rows=2 app_task=%d total=%d | rows=20 app_task=%d total=%d"
              % (small_task_queries, small_total, large_task_queries, large_total))

    def test_task_counts_add_no_statements_per_row(self):
        # Passing check for the new counts only: the correlated count subqueries
        # appear inside the list statement (and its COUNT wrapper), never per row.
        user = User.objects.create_user(username="qcuser2", email="qc2@test.com", password="test1234")
        client = self.client_for(user)

        def count_subquery_statements(query):
            with CaptureQueriesContext(connection) as ctx:
                res = client.get(LIST_URL + query)
            self.assertEqual(res.status_code, status.HTTP_200_OK)
            return len([q for q in ctx.captured_queries if 'COUNT(U0."id")' in q['sql']])

        self.add_query_count_projects(user, 2, 0)
        small = count_subquery_statements("?page=1&page_size=20")
        self.add_query_count_projects(user, 18, 2)
        large = count_subquery_statements("?page=1&page_size=20")

        self.assertGreater(small, 0)
        self.assertEqual(small, large)
        self.assertLessEqual(large, 2)

    # ------------------------------------------------------------------
    # Response shape
    # ------------------------------------------------------------------

    def test_task_counts_shape(self):
        project = self.make_project("Shape project")
        make_task(project, QUEUED)
        client = self.client_for(self.owner)

        # List: task_counts present with exactly these keys
        rows = {r['id']: r for r in rows_of(client.get(LIST_URL + "?page=1&page_size=20"))}
        self.assertEqual(set(rows[project.id]['task_counts'].keys()), {'total', 'queued', 'running', 'failed'})
        self.assertEqual(rows[project.id]['task_counts']['queued'], 1)

        # Detail: unchanged, no task_counts
        res = client.get("/api/projects/{}/".format(project.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn('task_counts', res.data)
        self.assertIn('tasks', res.data)

        # Update: no task_counts
        res = client.patch("/api/projects/{}/".format(project.id), {'name': 'Shape renamed'}, format="json")
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertNotIn('task_counts', res.data)

        # Create: no task_counts (superuser bypasses the allocation gate)
        admin_client = self.client_for(self.admin)
        res = admin_client.post(LIST_URL, {'name': 'Shape created'}, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertNotIn('task_counts', res.data)

    # ------------------------------------------------------------------
    # Malformed boolean values
    # ------------------------------------------------------------------

    def test_malformed_boolean_returns_400(self):
        client = self.client_for(self.owner)
        for param in ['hide_empty', 'has_active_work']:
            for bad in ['maybe', '2', 'yes']:
                res = client.get(LIST_URL + "?%s=%s" % (param, bad))
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, msg=(param, bad))
                self.assertIn(param, res.data, msg=(param, bad))

                res = client.get(LIST_URL + "?page=1&%s=%s" % (param, bad))
                self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST, msg=("paged", param, bad))

    def test_valid_boolean_spellings_accepted(self):
        self.make_project("Bool project")
        client = self.client_for(self.owner)
        for value in ['true', 'TRUE', '1', 'false', 'FALSE', '0']:
            res = client.get(LIST_URL + "?hide_empty=%s&has_active_work=%s" % (value, value))
            self.assertEqual(res.status_code, status.HTTP_200_OK, msg=value)
