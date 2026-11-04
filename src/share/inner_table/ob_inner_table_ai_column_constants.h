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

#ifndef OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_
#define OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_

#include <stdint.h>

// Contest AI Column system tables. Keep in sync with
// ob_inner_table_schema_def.py (__all_ai_column / __all_ai_column_task).
// Full generate_inner_table_schema.py rebuild also emits these into
// ob_inner_table_schema_constants.h; this header lets DDL persist paths
// compile before/without regenerating the full constants file.

#ifndef OB_ALL_AI_COLUMN_TID
const uint64_t OB_ALL_AI_COLUMN_TID = 1131;
#endif
#ifndef OB_ALL_AI_COLUMN_TASK_TID
const uint64_t OB_ALL_AI_COLUMN_TASK_TID = 1132;
#endif

#ifndef OB_ALL_AI_COLUMN_TNAME
#define OB_ALL_AI_COLUMN_TNAME "oceanbase.__all_ai_column"
#endif
#ifndef OB_ALL_AI_COLUMN_TASK_TNAME
#define OB_ALL_AI_COLUMN_TASK_TNAME "oceanbase.__all_ai_column_task"
#endif

#endif /* OCEANBASE_SHARE_INNER_TABLE_OB_INNER_TABLE_AI_COLUMN_CONSTANTS_H_ */
