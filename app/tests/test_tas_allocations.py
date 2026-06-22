from django.test import SimpleTestCase, override_settings
from unittest.mock import patch

from app.services import tas_allocations


class TASAllocationsTest(SimpleTestCase):
    @override_settings(
        TAS_RESOURCE_FILTER=['LS6', 'Lonestar6'],
        TAS_DEFAULT_ALLOCATION='PT2050-DataX',
    )
    @patch('app.services.tas_allocations._projects_for_user')
    def test_lists_active_allocations_and_prefers_default(self, projects_for_user):
        projects_for_user.return_value = [
            {
                'chargeCode': 'OTHER',
                'title': 'Other Project',
                'allocations': [
                    {
                        'resource': 'LS6',
                        'status': 'Active',
                        'computeAllocated': 100,
                        'computeUsed': 1,
                    }
                ],
            },
            {
                'chargeCode': 'PT2050-DataX',
                'title': 'Default Project',
                'allocations': [
                    {
                        'resource': 'Lonestar6',
                        'status': 'Active',
                        'computeAllocated': 100,
                        'computeUsed': 10,
                    }
                ],
            },
            {
                'chargeCode': 'INACTIVE',
                'title': 'Inactive Project',
                'allocations': [
                    {
                        'resource': 'LS6',
                        'status': 'Inactive',
                    }
                ],
            },
            {
                'chargeCode': 'WRONGRESOURCE',
                'title': 'Wrong Resource Project',
                'allocations': [
                    {
                        'resource': 'Frontera',
                        'status': 'Active',
                    }
                ],
            },
        ]

        allocations = tas_allocations.list_active_allocations('wmobley')

        self.assertEqual([a['chargeCode'] for a in allocations], ['OTHER', 'PT2050-DataX'])
        self.assertEqual(tas_allocations.choose_default_allocation(allocations), 'PT2050-DataX')

    @override_settings(TAS_DEFAULT_ALLOCATION='PT2050-DataX')
    def test_default_falls_back_to_first_allocation(self):
        allocations = [{'chargeCode': 'FIRST'}, {'chargeCode': 'SECOND'}]
        self.assertEqual(tas_allocations.choose_default_allocation(allocations), 'FIRST')

    @override_settings(TAS_REQUIRED_ALLOCATIONS=[])
    def test_gate_disabled_allows_everyone(self):
        self.assertFalse(tas_allocations.allocation_gate_enabled())
        self.assertTrue(tas_allocations.user_has_required_allocation('anyone'))
        # Even an empty username is allowed when the gate is off
        self.assertTrue(tas_allocations.user_has_required_allocation(''))

    @override_settings(TAS_REQUIRED_ALLOCATIONS=['PT2050-DataX'], TAS_ALLOCATION_CACHE_SECONDS=0)
    @patch('app.services.tas_allocations.list_active_allocations')
    def test_gate_allows_user_with_matching_allocation(self, list_active):
        self.assertTrue(tas_allocations.allocation_gate_enabled())
        list_active.return_value = [{'chargeCode': 'PT2050-DataX'}]
        self.assertTrue(tas_allocations.user_has_required_allocation('wmobley'))

    @override_settings(TAS_REQUIRED_ALLOCATIONS=['PT2050-DataX'], TAS_ALLOCATION_CACHE_SECONDS=0)
    @patch('app.services.tas_allocations.list_active_allocations')
    def test_gate_blocks_user_without_matching_allocation(self, list_active):
        list_active.return_value = [{'chargeCode': 'SOME-OTHER'}]
        self.assertFalse(tas_allocations.user_has_required_allocation('outsider'))

    @override_settings(TAS_REQUIRED_ALLOCATIONS=['PT2050-DataX'], TAS_ALLOCATION_CACHE_SECONDS=0)
    def test_gate_blocks_empty_username(self):
        self.assertFalse(tas_allocations.user_has_required_allocation(''))
