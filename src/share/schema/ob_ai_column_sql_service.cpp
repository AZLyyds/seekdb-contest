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

#define USING_LOG_PREFIX SHARE_SCHEMA

#include "share/schema/ob_ai_column_sql_service.h"
#include "share/ob_dml_sql_splicer.h"
#include "share/inner_table/ob_inner_table_ai_column_constants.h"
#include "lib/string/ob_sql_string.h"
#include "lib/oblog/ob_log_module.h"

namespace oceanbase
{
namespace share
{
namespace schema
{
using namespace common;

namespace {
int parse_u64_after_key(const char *p, const char *end, const char *key, uint64_t &out)
{
  int ret = OB_SUCCESS;
  const int64_t key_len = static_cast<int64_t>(STRLEN(key));
  bool found = false;
  for (const char *q = p; q + key_len < end; ++q) {
    if (0 == STRNCMP(q, key, key_len)) {
      const char *cur = q + key_len;
      uint64_t v = 0;
      while (cur < end && *cur >= '0' && *cur <= '9') {
        v = v * 10 + static_cast<uint64_t>(*cur - '0');
        ++cur;
      }
      out = v;
      found = true;
      break;
    }
  }
  if (!found) {
    ret = OB_INVALID_ARGUMENT;
  }
  return ret;
}

int parse_i64_after_key(const char *p, const char *end, const char *key, int64_t &out)
{
  uint64_t tmp = 0;
  int ret = parse_u64_after_key(p, end, key, tmp);
  if (OB_SUCC(ret)) {
    out = static_cast<int64_t>(tmp);
  }
  return ret;
}
} // namespace

int ObAiColumnSqlService::parse_ai_meta_from_comment(const ObString &comment,
                                                     int64_t &max_retries,
                                                     int64_t &sync_mode,
                                                     uint64_t &state_column_id,
                                                     uint64_t &request_column_id,
                                                     uint64_t &result_spec_column_id,
                                                     ObString &normalized_expr)
{
  int ret = OB_SUCCESS;
  max_retries = 0;
  sync_mode = 0;
  state_column_id = 0;
  request_column_id = 0;
  result_spec_column_id = 0;
  normalized_expr.reset();
  if (!comment.prefix_match("__AI__|")) {
    ret = OB_INVALID_ARGUMENT;
  } else {
    const char *p = comment.ptr();
    const char *end = p + comment.length();
    (void)parse_i64_after_key(p, end, "mr=", max_retries);
    (void)parse_i64_after_key(p, end, "sm=", sync_mode);
    (void)parse_u64_after_key(p, end, "st=", state_column_id);
    (void)parse_u64_after_key(p, end, "rq=", request_column_id);
    (void)parse_u64_after_key(p, end, "rs=", result_spec_column_id);
    for (const char *q = p; q + 5 <= end; ++q) {
      if (0 == STRNCMP(q, "expr=", 5)) {
        normalized_expr.assign_ptr(q + 5, static_cast<int32_t>(end - (q + 5)));
        break;
      }
    }
  }
  return ret;
}

int ObAiColumnSqlService::insert_ai_column(ObISQLClient &sql_client,
                                           const uint64_t table_id,
                                           const ObColumnSchemaV2 &ai_column)
{
  int ret = OB_SUCCESS;
  if (!ai_column.is_ai_column()) {
    // ignore
  } else {
    int64_t max_retries = 0;
    int64_t sync_mode = 0;
    uint64_t state_id = 0;
    uint64_t request_id = 0;
    uint64_t rspec_id = 0;
    ObString expr;
    if (OB_FAIL(parse_ai_meta_from_comment(ai_column.get_comment(),
                                           max_retries, sync_mode,
                                           state_id, request_id, rspec_id, expr))) {
      LOG_WARN("failed to parse AI column meta from comment", K(ret),
               K(ai_column.get_column_name_str()), K(ai_column.get_comment()));
    } else {
      ObDMLSqlSplicer sql;
      ObSqlString buffer;
      int64_t affected_rows = 0;
      if (OB_FAIL(sql.add_pk_column("table_id", table_id))) {
      } else if (OB_FAIL(sql.add_pk_column("column_id", ai_column.get_column_id()))) {
      } else if (OB_FAIL(sql.add_column("column_name",
                                        ObHexEscapeSqlStr(ai_column.get_column_name_str())))) {
      } else if (OB_FAIL(sql.add_column("max_retries", max_retries))) {
      } else if (OB_FAIL(sql.add_column("sync_mode", sync_mode))) {
      } else if (OB_FAIL(sql.add_column("normalized_expr", ObHexEscapeSqlStr(expr)))) {
      } else if (OB_FAIL(sql.add_column("state_column_id", state_id))) {
      } else if (OB_FAIL(sql.add_column("request_column_id", request_id))) {
      } else if (OB_FAIL(sql.add_column("result_spec_column_id", rspec_id))) {
      } else if (OB_FAIL(sql.splice_insert_sql(OB_ALL_AI_COLUMN_TNAME, buffer))) {
      } else if (OB_FAIL(sql_client.write(buffer.ptr(), affected_rows))) {
        LOG_WARN("failed to insert __all_ai_column", K(ret), K(buffer));
      } else if (1 != affected_rows) {
        ret = OB_ERR_UNEXPECTED;
        LOG_WARN("unexpected affected rows for __all_ai_column insert",
                 K(ret), K(affected_rows), K(buffer));
      }
    }
  }
  return ret;
}

int ObAiColumnSqlService::insert_ai_columns_for_table(ObISQLClient &sql_client,
                                                      const ObTableSchema &table_schema)
{
  int ret = OB_SUCCESS;
  ObTableSchema::const_column_iterator it = table_schema.column_begin();
  ObTableSchema::const_column_iterator end = table_schema.column_end();
  for (; OB_SUCC(ret) && it != end; ++it) {
    const ObColumnSchemaV2 *col = *it;
    if (OB_ISNULL(col)) {
      ret = OB_ERR_UNEXPECTED;
    } else if (col->is_ai_column()) {
      if (OB_FAIL(insert_ai_column(sql_client, table_schema.get_table_id(), *col))) {
      }
    }
  }
  return ret;
}

int ObAiColumnSqlService::delete_ai_column(ObISQLClient &sql_client,
                                           const uint64_t table_id,
                                           const uint64_t column_id)
{
  int ret = OB_SUCCESS;
  ObDMLSqlSplicer sql;
  ObSqlString buffer;
  int64_t affected_rows = 0;
  if (OB_FAIL(sql.add_pk_column("table_id", table_id))) {
  } else if (OB_FAIL(sql.add_pk_column("column_id", column_id))) {
  } else if (OB_FAIL(sql.splice_delete_sql(OB_ALL_AI_COLUMN_TNAME, buffer))) {
  } else if (OB_FAIL(sql_client.write(buffer.ptr(), affected_rows))) {
    LOG_WARN("failed to delete __all_ai_column row", K(ret), K(buffer));
  }
  return ret;
}

int ObAiColumnSqlService::delete_ai_columns_for_table(ObISQLClient &sql_client,
                                                      const uint64_t table_id)
{
  int ret = OB_SUCCESS;
  ObSqlString buffer;
  int64_t affected_rows = 0;
  if (OB_FAIL(buffer.assign_fmt("DELETE FROM %s WHERE table_id = %lu",
                                OB_ALL_AI_COLUMN_TNAME, table_id))) {
  } else if (OB_FAIL(sql_client.write(buffer.ptr(), affected_rows))) {
    LOG_WARN("failed to delete __all_ai_column rows for table", K(ret), K(table_id));
  } else {
    ObSqlString task_buf;
    if (OB_FAIL(task_buf.assign_fmt("DELETE FROM %s WHERE table_id = %lu",
                                    OB_ALL_AI_COLUMN_TASK_TNAME, table_id))) {
    } else if (OB_FAIL(sql_client.write(task_buf.ptr(), affected_rows))) {
      LOG_WARN("failed to delete __all_ai_column_task rows for table", K(ret), K(table_id));
    }
  }
  return ret;
}

} // namespace schema
} // namespace share
} // namespace oceanbase
