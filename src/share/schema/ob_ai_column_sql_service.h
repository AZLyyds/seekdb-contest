/*
 * Copyright (c) 2025 OceanBase.
 *
 * Licensed under the Apache License, Version 2.0 (the "License");
 * you may not use this file except in compliance with the License.
 * You may obtain a copy of the License at
 *
 *     http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing, software
 * distributed under the License is distributed on an "AS IS" BASIS,
 * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 * See the License for the specific language governing permissions and
 * limitations under the License.
 */

#ifndef OCEANBASE_SHARE_SCHEMA_OB_AI_COLUMN_SQL_SERVICE_H_
#define OCEANBASE_SHARE_SCHEMA_OB_AI_COLUMN_SQL_SERVICE_H_

#include "lib/mysqlclient/ob_isql_client.h"
#include "share/schema/ob_column_schema.h"
#include "share/schema/ob_table_schema.h"

namespace oceanbase
{
namespace share
{
namespace schema
{

// Persist / cleanup rows in oceanbase.__all_ai_column for AI COLUMN DDL.
class ObAiColumnSqlService
{
public:
  // Parse "__AI__|mr=..|sm=..|st=..|rq=..|rs=..|expr=.." from column comment.
  static int parse_ai_meta_from_comment(const common::ObString &comment,
                                        int64_t &max_retries,
                                        int64_t &sync_mode,
                                        uint64_t &state_column_id,
                                        uint64_t &request_column_id,
                                        uint64_t &result_spec_column_id,
                                        common::ObString &normalized_expr);

  static int insert_ai_column(common::ObISQLClient &sql_client,
                              const uint64_t table_id,
                              const ObColumnSchemaV2 &ai_column);

  static int insert_ai_columns_for_table(common::ObISQLClient &sql_client,
                                         const ObTableSchema &table_schema);

  static int delete_ai_column(common::ObISQLClient &sql_client,
                              const uint64_t table_id,
                              const uint64_t column_id);

  static int delete_ai_columns_for_table(common::ObISQLClient &sql_client,
                                         const uint64_t table_id);

private:
  DISALLOW_COPY_AND_ASSIGN(ObAiColumnSqlService);
};

} // namespace schema
} // namespace share
} // namespace oceanbase

#endif // OCEANBASE_SHARE_SCHEMA_OB_AI_COLUMN_SQL_SERVICE_H_
