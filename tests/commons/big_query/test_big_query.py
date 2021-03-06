import unittest

from apiclient.errors import HttpError
from apiclient.http import HttpMockSequence
from google.appengine.ext import testbed
from mock import patch

from src.commons.big_query.big_query import BigQuery, TableNotFoundException
from tests.test_utils import content


class TestBigQuery(unittest.TestCase):
    def setUp(self):
        self.testbed = testbed.Testbed()
        self.testbed.activate()
        self.testbed.init_memcache_stub()
        self.testbed.init_app_identity_stub()
        self._create_http = patch.object(BigQuery, '_create_http').start()

    def tearDown(self):
        patch.stopall()
        self.testbed.deactivate()

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_iterating_projects(self, _):
        # given
        self._create_http.return_value = self.__create_project_list_responses()
        bq = BigQuery()
        # when
        project_ids, next_page_token = bq.list_project_ids()

        # then
        self.assertEqual(self.count(project_ids), 3)
        self.assertEqual(next_page_token, '3')

        # when (next_page_token)
        project_ids, next_page_token = bq.list_project_ids(
            page_token=next_page_token)
        # then
        self.assertEqual(self.count(project_ids), 1)
        self.assertEqual(next_page_token, None)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_iterating_datasets(self, _):
        # given
        self._create_http.return_value = self.__create_dataset_list_responses()
        bq = BigQuery()
        # when
        dataset_ids, next_page_token = bq.list_dataset_ids("project123")

        # then
        self.assertEqual(self.count(dataset_ids), 2)
        self.assertEqual(next_page_token, 'FMLMpsxvgM')

        # when
        dataset_ids, next_page_token = bq.list_dataset_ids("project123",
                                                           page_token=next_page_token)

        # then
        self.assertEqual(self.count(dataset_ids), 1)
        self.assertEqual(next_page_token, None)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_iterating_tables(self, _):
        # given
        self._create_http.return_value = self.__create_tables_list_responses()
        bq = BigQuery()
        # when
        tables_ids, next_page_token = bq.list_table_ids("project1233",
                                                        "dataset_id")

        # then
        self.assertEqual(self.count(tables_ids), 4)
        self.assertEqual(next_page_token, 'table_id_5')

        # when
        tables_ids, next_page_token = bq.list_table_ids("project1233",
                                                        "dataset_id",
                                                        page_token=next_page_token)

        # then
        self.assertEqual(self.count(tables_ids), 1)
        self.assertEqual(next_page_token, None)

    @patch('time.sleep', side_effect=lambda _: None)
    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_iterating_tables_retries_if_503_returned(self, _1, _2):
        # given
        self._create_http.return_value = self.__create_tables_list_responses_with_503()
        bq = BigQuery()
        # when
        tables_ids, next_page_token = bq.list_table_ids("project1233",
                                                        "dataset_id")

        # then
        self.assertEqual(self.count(tables_ids), 4)
        self.assertEqual(next_page_token, 'table_id_5')

        # when
        tables_ids, next_page_token = bq.list_table_ids("project1233",
                                                        "dataset_id",
                                                        page_token=next_page_token)

        # then
        self.assertEqual(self.count(tables_ids), 1)
        self.assertEqual(next_page_token, None)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_iterating_tables_when_dataset_not_exist_then_iterating_tables_should_not_return_any_table(
        self, _):
        # given
        self._create_http.return_value = self.__create_dataset_not_found_during_tables_list_responses()

        # when
        tables_ids, next_page_token = BigQuery().list_table_ids("projectid",
                                                                "dataset_id")

        # then
        self.assertEqual(self.count(tables_ids), 0)
        self.assertEqual(next_page_token, None)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_insert_job_forwarding_409_error(self, _):
        # given
        self._create_http.return_value = self.__create_409_response()

        # when
        with self.assertRaises(HttpError) as context:
            BigQuery().insert_job('project_id', {})

        # then
        self.assertEqual(context.exception.resp.status, 409)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_insert_job_forwarding_503_error(self, _):
        # given
        self._create_http.return_value = self.__create_503_response()

        # when
        with self.assertRaises(HttpError) as context:
            BigQuery().insert_job('project_id', {})

        # then
        self.assertEqual(context.exception.resp.status, 503)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_listing_table_partitions(self, _):
        # given
        self._create_http.return_value = self.__create_table_partititions_list_responses()
        # when
        partitions = BigQuery() \
            .list_table_partitions("project123", "dataset123", "table123")

        # then
        self.assertEqual(self.count(partitions), 5)
        self.assertEqual(partitions[0]['partitionId'], '20170317')
        self.assertEqual(partitions[0]['creationTime'],
                         '2017-03-17 14:32:17.755000')
        self.assertEqual(partitions[0]['lastModifiedTime'],
                         '2017-03-17 14:32:19.289000')

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_listing_table_partitions_when_table_not_exist_should_throw_table_not_found_exception(
        self, _):
        # given
        self._create_http.return_value = self.__create_table_partititions_list_responses_table_404_not_found()
        # when & then
        with self.assertRaises(TableNotFoundException) as exception:
            BigQuery().list_table_partitions("project123", "dataset123",
                                             "table123")

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_get_dataset_cached_should_only_call_bq_once_but_response_is_cached(
        self, _):
        # given
        self._create_http.return_value = \
            self.__create_dataset_responses_with_only_one_response_for_get_dataset()
        # when
        bq = BigQuery()
        result1 = bq.get_dataset_cached('project', 'dataset')
        result2 = bq.get_dataset_cached('project', 'dataset')

        # then
        self.assertEqual(result1, result2)

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_create_dataset_happy_path(self, _):
        # given
        self._create_http.return_value = self.__create_dataset_create_responses()
        # when then
        BigQuery().create_dataset("project123", "dataset_id", "US")

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_create_dataset_do_nothing_if_dataset_already_exists(self, _):
        # given
        self._create_http.return_value = self.__create_dataset_create_already_exist_responses()
        # when then
        BigQuery().create_dataset("project123", "dataset_id", "US")

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_create_dataset_do_nothing_if_access_denied(self, _):
        # given
        self._create_http.return_value = self.__create_access_denied_response()
        # when then
        BigQuery().create_dataset("project123", "dataset_id", "US")

    @staticmethod
    def count(generator):
        return sum(1 for _ in generator)

    @staticmethod
    def __create_project_list_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_project_list_page_1.json')),
            ({'status': '200'}, content(
                'tests/json_samples/bigquery_project_list_page_last.json'))
        ])

    @staticmethod
    def __create_dataset_list_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_dataset_list_page_1.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_dataset_list_page_last.json'))
        ])

    @staticmethod
    def __create_get_table_400_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '400'},
             content(
                 'tests/json_samples/table_get/bigquery_view_get_400_read_partition.json'))
        ])

    @staticmethod
    def __create_409_response():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '409'},
             content('tests/json_samples/bigquery_409_error.json'))
        ])

    @staticmethod
    def __create_503_response():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '503'},
             content('tests/json_samples/bigquery_503_error.json'))
        ])

    @staticmethod
    def __create_tables_list_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_table_list_page_1.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_table_list_page_last.json'))
        ])

    @patch.object(BigQuery, '_create_credentials', return_value=None)
    def test_execute_query_when_executing_long_query(self, _):
        # given
        self._create_http.return_value = self.__execute_long_query_responses()
        # when
        result = BigQuery().execute_query("SELECT * FROM tableXYZ")
        # then
        self.assertEqual(result, [
            {
                "f": [
                    {
                        "v": "a-gcp-project2"
                    },
                    {
                        "v": "test1"
                    }
                ]
            },
            {
                "f": [
                    {
                        "v": "a-gcp-project3"
                    },
                    {
                        "v": "smoke_test_US"
                    }
                ]
            }
        ])

    @staticmethod
    def __execute_long_query_responses():
        return HttpMockSequence([
            ({'status': '200'}, content(
                'tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/big_query/query_response.json')),
            ({'status': '200'}, content(
                'tests/json_samples/big_query/get_query_results_job_not_completed.json')),
            ({'status': '200'}, content(
                'tests/json_samples/big_query/get_query_results_job_completed.json'))
        ])

    @staticmethod
    def __create_dataset_not_found_during_tables_list_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/bigquery_table_list_404_dataset_not_exist.json'))
        ])

    @staticmethod
    def __create_table_partititions_list_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_query_for_partitions.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/bigquery_query_for_partitions_results_1.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/bigquery_query_for_partitions_results_last.json'))
        ])

    @staticmethod
    def __create_table_partititions_list_responses_table_404_not_found():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '404'},
             content(
                 'tests/json_samples/bigquery_partition_query_404_table_not_exist.json'))
        ])

    @staticmethod
    def __create_random_table_responses():
        return HttpMockSequence([(
            {'status': '200'},
            content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/random_table/biquery_query_for_random_table.json'))
        ])

    @staticmethod
    def __create_table_responses_with_only_one_response_for_get_table():
        return HttpMockSequence([(
            {'status': '200'},
            content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/random_table/biquery_query_for_random_table.json'))
        ])

    @staticmethod
    def __create_dataset_responses_with_only_one_response_for_get_dataset():
        return HttpMockSequence([(
            {'status': '200'},
            content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_dataset_create.json')), ])

    @staticmethod
    def __create_random_table_no_results_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content(
                 'tests/json_samples/random_table/big_query_for_random_table_no_results.json'))
        ])

    @staticmethod
    def __create_dataset_create_responses():
        return HttpMockSequence([(
            {'status': '200'},
            content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_dataset_create.json')), ])

    @staticmethod
    def __create_dataset_create_already_exist_responses():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '409'},
             content('tests/json_samples/bigquery_dataset_create.json')), ])

    @staticmethod
    def __create_access_denied_response():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '403'},
             content('tests/json_samples/bigquery_access_denied.json')), ])

    @staticmethod
    def __create_tables_list_responses_with_503():
        return HttpMockSequence([
            ({'status': '200'},
             content('tests/json_samples/bigquery_v2_test_schema.json')),
            ({'status': '503'},
             content('tests/json_samples/bigquery_503_error.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_table_list_page_1.json')),
            ({'status': '200'},
             content('tests/json_samples/bigquery_table_list_page_last.json'))
        ])
