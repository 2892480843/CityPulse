import { getJson, patchJson, postJson } from '../../shared/api/client'
import type { RoleName, UserAdminView, UserListResponse } from '../../shared/api/types'

export const listUsers = () => getJson<UserListResponse>('/api/v1/admin/users')

export const createUser = (payload: {
  username: string
  password: string
  display_name: string
  roles: RoleName[]
}) => postJson<UserAdminView>('/api/v1/admin/users', payload)

export const updateUser = (
  id: string,
  payload: { display_name?: string; is_active?: boolean; roles?: RoleName[] },
) => patchJson<UserAdminView>(`/api/v1/admin/users/${id}`, payload)
