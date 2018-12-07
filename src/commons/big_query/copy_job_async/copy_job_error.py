class CopyJobError(object):
    def __init__(self, bq_error, source_bq_table, target_bq_table):
        self.bq_error = bq_error
        self.source_bq_table = source_bq_table
        self.target_bq_table = target_bq_table
        self.reason = self.__get_reason()

    def __str__(self):
        return "{} while creating Copy Job from {} to {}" \
            .format(self.reason, self.source_bq_table, self.target_bq_table)

    def should_be_retried(self):
        if self.__is_access_denied() or self.__is_404():
            return False
        elif self.__is_409():
            return True
        else:
            raise self.bq_error

    def __is_access_denied(self):
        return self.bq_error.resp.status == 403 and \
               self.bq_error._get_reason().startswith('Access Denied')

    def __is_404(self):
        return self.bq_error.resp.status == 404

    def __is_409(self):
        return self.bq_error.resp.status == 409

    def __get_reason(self):
        if self.__is_access_denied():
            return 'Access Denied'
        elif self.__is_404():
            return '404'
        elif self.__is_409():
            return '409'
        else:
            return 'Unknown reason'

    def to_json(self):
        return {
            "status": {
                "state": "DONE",
                "errors": [
                    {
                        "reason": self.reason,
                        "message": self.__str__()
                    }
                ]
            },
            "configuration": {
                "copy": {
                    "sourceTable": {
                        "projectId": self.source_bq_table.get_project_id(),
                        "tableId": self.source_bq_table.get_table_id(),
                        "datasetId": self.source_bq_table.get_dataset_id()
                    },
                    "destinationTable": {
                        "projectId": self.target_bq_table.get_project_id(),
                        "tableId": self.target_bq_table.get_table_id(),
                        "datasetId": self.target_bq_table.get_dataset_id()
                    }
                }
            }
        }
