from abc import abstractmethod
import asyncio
import json
from typing import Optional, List, Dict, Any, Union, Set, Callable

from sdk.commands.data import Joint, Point, Pose, Point3D
from sdk.commands.move_group import MoveGroup, MoveType
from sdk.commands.abstracts.sdk_command import SdkCommand
from sdk.commands.get_manage_command import GetManageCommand
from sdk.commands.play_audio_command import PlayAudioCommand
from sdk.commands.move_angles_command import MoveAnglesCommand, MoveAnglesCommandParamsAngleInfo
from sdk.commands.set_conveyor_velocity_command import SetConveyorVelocityCommand
from sdk.commands.calibration_linear_module_command import CalibrateControllerCommand
from sdk.commands.move_linear_module_command import MoveLinearModuleCommand
from sdk.manipulators.extern_devices.pixy_cam.pixy_cam_uart_module import PixyCamUartModule
from sdk.manipulators.extern_devices.pixy_cam.pixy_cam_usb_module import PixyCamUsbModule
from sdk.manipulators.extern_devices.mgbot.mgbot_conveyer import MGbotConveyer
from sdk.commands.pixy_cam_get_coordinates_command import PixyCamGetCoordinatesCommand
from sdk.commands.move_coordinates_command import MoveCoordinatesCommand, MoveCoordinatesParams, \
    MoveCoordinatesParamsPosition, MoveCoordinatesParamsOrientation, PlannerType
from sdk.commands.manipulator_commands import SetStateCommand, TCPAdd, GetGpio, SetJointLimits, GetJointLimits, \
    JointLimit, WriteAnalogOutputCommand, WriteDigitalOutputCommand, TCPDelete, TCPApply, TCPGetCurrent, TCPGetList
from sdk.manipulators.manipulator_info import ManipulatorInfo
from sdk.commands.arc_motion import ArcMotion, Pose
from sdk.manipulators.manipulator_connection import ManipulatorConnection
from sdk.promise import Promise
from sdk.utils.constants import COMMAND_TOPIC, MANAGEMENT_TOPIC, CARTESIAN_COORDINATES_TOPIC, JOINT_INFO_TOPIC, \
    COMMAND_RESULT_TOPIC, COMMAND_FEEDBACK_TOPIC, PIXY_CAM_COORDINATES_TOPIC, MGBOT_TOPIC
from sdk.commands import (
    RunProgramJsonCommand,
    RunProgramByNameCommand,
    RunPythonProgramCommand,
    StopMovementCommand,
    SetZeroZCommand,
    WriteI2C,
    WriteGPIO
)
from sdk.commands.servo_control_type_command import ServoControlTypeCommand, JOINT_JOG, TWIST, POSE
from sdk.utils.enums import ManipulatorState, ServoControlType
from sdk.commands.abstracts.sdk_command import NoWaitCommand


class Manipulator:
    message_bus: ManipulatorConnection

    def __init__(self, host: str, client_id: str, login: str, password: str):
        self.host = host
        self.client_id = client_id
        self.login = login
        self.password = password
        self.message_bus = ManipulatorConnection(host, client_id, login, password, self.process_message)
        self.message_bus._manipulator_ref = self
        self.pixy_cam_uart_control = PixyCamUartModule(self.message_bus, self._run_async, self)
        self.pixy_cam_usb_control = PixyCamUsbModule(self.message_bus, self._run_async, self)
        self.mgbot_conveyer = MGbotConveyer(self.message_bus, self._run_async, self)

        self.last_cartesian_coordinates: Optional[str] = None
        self.last_pixy_coordinates: Optional[str] = None
        self.last_joint_state: Optional[str] = None
        self.promise: Promise = None

        self.manage_command: GetManageCommand | None = None
        self.specific_command: SdkCommand | None = None
        self.move_coordinates_command: MoveCoordinatesCommand | None = None
        self.move_angles_command: MoveAnglesCommand | None = None

        self.active_commands: Dict[int, object] = {}

        self.cartesian_coordinates_promise: Promise | None = None
        self.joint_state_promise: Promise | None = None
        self.pixy_coordinates_promise: Optional[Promise] = None

        self.last_cartesian_coordinates: str | None = None
        self.last_pixy_coordinates: Optional[str] = None
        self.last_joint_state: str | None = None

        self.info = ManipulatorInfo(self.message_bus)
        self.info._manipulator_ref = self

        self._user_message_handler = None
        self._topic_handlers: Dict[str, Callable[[Dict[str, Any]], None]] = {}

        self._attachments: List[Any] = []

    def register_attachment(self, attachment: Any) -> None:
        """
        Зарегистрировать насадку в манипуляторе
        :param attachment: Объект насадки
        """
        self._attachments.append(attachment)
        try:
            if hasattr(attachment, "attach"):
                attachment.attach(self)
        except Exception as e:
            print(f"Ошибка при attach насадки {attachment}: {e}")

    def unregister_attachment(self, attachment: Any) -> None:
        """
        Удалить насадку из манипулятора
        :param attachment: Объект насадки
        """
        if attachment in self._attachments:
            try:
                if hasattr(attachment, "detach"):
                    attachment.detach()
            except Exception as e:
                print(f"Ошибка при detach насадки {attachment}: {e}")
            self._attachments.remove(attachment)

    def list_attachments(self) -> List[Any]:
        """
        Получить список всех зарегистрированных насадок
        :return: Список насадок
        """
        return self._attachments

    def _on_run_success(self, result: Any) -> None:
        print(f"{self.specific_command} завершился, результат = {result}")

    def _on_run_failure(self, error: Exception) -> None:
        print(f"{self.specific_command} с ошибкой: {error}")

    def _on_run_feedback(self, feedback: dict) -> None:
        """
        Обрабатывает все промежуточные статусы узлов.
        Выводит любой переход статуса.
        При возникновении FAILURE также реджектим промис.
        """
        node = feedback.get('node_name')
        prev = feedback.get('previous_status')
        curr = feedback.get('current_status')

        print(f"[Feedback] {node}: {prev} → {curr}")

        if curr == 'FAILURE':
            if self.promise and self.promise.is_active:
                self.promise.reject(Exception(f"{node} → FAILURE"))

    def connect(self) -> None:
        self.message_bus.connect()

    async def connect_async(self) -> None:
        await self.message_bus.connect_async()

    def process_message(self, topic: str, payload: str) -> None:
        # Фильтруем частые потоковые сообщения для оптимизации
        is_streaming_topic = topic in ["/joint_states", "/coordinates", "/gpio_states"]

        if not is_streaming_topic:
            import time
            print(f"[MANIPULATOR] process_message в {time.time()}")
            print(f"[MANIPULATOR] Топик: {topic}")
            print(f"[MANIPULATOR] Payload: {payload.encode().decode('unicode_escape')}")

        # Специальная обработка для ответов команд
        if topic == COMMAND_RESULT_TOPIC:
            import json
            try:
                data = json.loads(payload)
                command_id = data.get("id")
                result = data.get("result")
                print(f"[MANIPULATOR] Ответ команды ID={command_id}, result={result}")

                command_found_in_active = False
                if hasattr(self, 'active_commands') and self.active_commands and command_id in self.active_commands:
                    print(f"[MANIPULATOR] Передаем в active_commands[{command_id}]")
                    self.active_commands[command_id].process_message(topic, payload)
                    command_found_in_active = True
                    # Команда найдена и обработана – больше ничего делать не нужно
                    return

                if not command_found_in_active and hasattr(self,
                                                           'move_angles_command') and self.move_angles_command and self.move_angles_command.command_id == command_id:
                    print(f"[MANIPULATOR] Передаем в move_angles_command")
                    self.move_angles_command.process_message(topic, payload)
                    return
                elif not command_found_in_active and hasattr(self,
                                                             'specific_command') and self.specific_command and self.specific_command.command_id == command_id:
                    print(f"[MANIPULATOR] Передаем в specific_command")
                    self.specific_command.process_message(topic, payload)
                    return
                elif not command_found_in_active and hasattr(self,
                                                             'manage_command') and self.manage_command and self.manage_command.command_id == command_id:
                    print(f"[MANIPULATOR] Передаем в manage_command (ID сопоставлен: {command_id})")
                    self.manage_command.process_message(topic, payload)
                    return
                elif not command_found_in_active and hasattr(self,
                                                             'move_coordinates_command') and self.move_coordinates_command and self.move_coordinates_command.command_id == command_id:
                    print(f"[MANIPULATOR] Передаем в move_coordinates_command")
                    self.move_coordinates_command.process_message(topic, payload)
                    return
            except Exception as e:
                print(f"[MANIPULATOR] Ошибка обработки ответа: {e}")

        if not is_streaming_topic:
            print(f"[MANIPULATOR] Передаем в info.process_message...")
        self.info.process_message(topic, payload)

        # Для потоковых топиков проверяем только активные команды
        if is_streaming_topic:
            # Быстрая проверка активных команд для потоковых сообщений
            if self.manage_command and self.manage_command.promise.is_active:
                self.manage_command.process_message(topic, payload)
            if self.move_coordinates_command and self.move_coordinates_command.promise.is_active:
                self.move_coordinates_command.process_message(topic, payload)
            if self.move_angles_command and self.move_angles_command.promise.is_active:
                self.move_angles_command.process_message(topic, payload)
            if self.specific_command and self.specific_command.promise.is_active:
                self.specific_command.process_message(topic, payload)
        else:
            # Для остальных топиков обрабатываем все команды с логированием
            if not self.manage_command is None:
                print(f"[MANIPULATOR] Передаем в manage_command.process_message...")
                self.manage_command.process_message(topic, payload)

            if not self.move_coordinates_command is None:
                print(f"[MANIPULATOR] Передаем в move_coordinates_command.process_message...")
                self.move_coordinates_command.process_message(topic, payload)

            if not self.move_angles_command is None:
                print(f"[MANIPULATOR] Передаем в move_angles_command.process_message...")
                self.move_angles_command.process_message(topic, payload)

            if not self.specific_command is None:
                print(f"[MANIPULATOR] Передаем в specific_command.process_message...")
                print(f"[MANIPULATOR] specific_command тип: {type(self.specific_command).__name__}")
                self.specific_command.process_message(topic, payload)
            else:
                print(f"[MANIPULATOR] specific_command равен None")

        if hasattr(self, 'active_commands') and self.active_commands and is_streaming_topic:
            for cmd_id, command in list(self.active_commands.items()):
                if hasattr(command, 'promise') and command.promise.is_active:
                    try:
                        command.process_message(topic, payload)
                    except Exception as e:
                        pass

        if topic == MGBOT_TOPIC:
            print(f"[MANIPULATOR] MGBOT_TOPIC: {payload}")

            try:
                import json
                data = json.loads(payload)
                if 'DistanceSensor' in data['data'] or 'ColorSensor' in data['data']:
                    self.mgbot_conveyer.last_sensor_data = data['data']
                    self.mgbot_conveyer.mgbot_promise.resolve(True)
            except Exception as e:
                print(f"[MANIPULATOR] Ошибка: {e}")

        if topic == PIXY_CAM_COORDINATES_TOPIC:
            self.last_pixy_coordinates = payload
            self.pixy_coordinates_promise.resolve(True)

        if not self.cartesian_coordinates_promise is None and topic == CARTESIAN_COORDINATES_TOPIC:
            p = self.cartesian_coordinates_promise
            print(f"[MANIPULATOR] Обрабатываем cartesian_coordinates_promise...")
            self.last_cartesian_coordinates = payload
            if p is not None:
                p.resolve(True)

        if not self.joint_state_promise is None and topic == JOINT_INFO_TOPIC:
            print(f"[MANIPULATOR] Обрабатываем joint_state_promise...")
            self.last_joint_state = payload
            self.joint_state_promise.resolve(True)

        # Вызываем пользовательский обработчик, если установлен
        if self._user_message_handler is not None:
            print(f"[MANIPULATOR] Вызываем пользовательский обработчик...")
            try:
                self._user_message_handler(topic, payload)
            except Exception as e:
                print(f"Ошибка в пользовательском обработчике сообщений: {e}")

        # Вызываем обработчик для конкретного топика, если он есть
        if topic in self._topic_handlers:
            print(f"[MANIPULATOR] Вызываем обработчик для топика {topic}...")
            try:
                import json as json_module
                data = json_module.loads(payload)
                self._topic_handlers[topic](data)
            except json_module.JSONDecodeError:
                print(f"Ошибка декодирования JSON из топика {topic}: {payload}")
            except Exception as e:
                print(f"Ошибка в обработчике для топика {topic}: {e}")

        if not is_streaming_topic:
            print(f"[MANIPULATOR] process_message завершен")

    async def _run_async(self, sync_func, *args, **kwargs):
        """
        Выполняет синхронную функцию в пуле потоков асинхронно
        :param sync_func: Синхронная функция для выполнения
        :param args: Позиционные аргументы для функции
        :param kwargs: Именованные аргументы для функции
        :return: Результат выполнения функции
        """
        return await asyncio.to_thread(sync_func, *args, **kwargs)

    # Асинхронные методы для существующих команд
    def get_control_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> GetManageCommand:
        self.manage_command = GetManageCommand(
            self.message_bus.publish,
            self.client_id,
            timeout_seconds,
            throw_error,
            self.message_bus
        )
        self.message_bus.subscribe(MANAGEMENT_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.active_commands[self.manage_command.command_id] = self.manage_command
        return self.manage_command

    async def get_control_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        # Выполняем синхронную версию в пуле потоков
        await self._run_async(self.get_control, timeout_seconds, throw_error)

    def get_control(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.get_control_async(timeout_seconds, throw_error)
        command.make_command_action()
        try:
            command.result()
        finally:
            self.manage_command = None

    def move_to_coordinates_async(self,
                                  position: MoveCoordinatesParamsPosition,
                                  orientation: MoveCoordinatesParamsOrientation,
                                  velocity_scaling_factor: float,
                                  acceleration_scaling_factor: float,
                                  planner_type: PlannerType = PlannerType.LIN,
                                  timeout_seconds: float = 60.0,
                                  throw_error: bool = True) -> MoveCoordinatesCommand:
        parameters = MoveCoordinatesParams(position, orientation, velocity_scaling_factor, acceleration_scaling_factor,
                                           planner_type)
        self.move_coordinates_command = MoveCoordinatesCommand(self.message_bus.publish, parameters, timeout_seconds,
                                                               throw_error, self.message_bus)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.active_commands[self.move_coordinates_command.command_id] = self.move_coordinates_command
        return self.move_coordinates_command

    async def move_to_coordinates_async_await(self,
                                              position: MoveCoordinatesParamsPosition,
                                              orientation: MoveCoordinatesParamsOrientation,
                                              velocity_scaling_factor: float,
                                              acceleration_scaling_factor: float,
                                              planner_type: PlannerType = PlannerType.LIN,
                                              timeout_seconds: float = 60.0,
                                              throw_error: bool = True) -> None:
        await self._run_async(
            self.move_to_coordinates,
            position,
            orientation,
            velocity_scaling_factor,
            acceleration_scaling_factor,
            planner_type,
            timeout_seconds,
            throw_error,
        )

    def move_to_coordinates(self,
                            position: MoveCoordinatesParamsPosition,
                            orientation: MoveCoordinatesParamsOrientation,
                            velocity_scaling_factor: float,
                            acceleration_scaling_factor: float,
                            planner_type: PlannerType = PlannerType.LIN,
                            timeout_seconds: float = 60.0,
                            throw_error: bool = True) -> None:
        command = self.move_to_coordinates_async(
            position,
            orientation,
            velocity_scaling_factor,
            acceleration_scaling_factor,
            planner_type,
            timeout_seconds,
            throw_error
        )
        command.make_command_action()  # Отправляем команду
        try:
            command.result()
        finally:
            self.move_coordinates_command = None

    def _run_move_to_angles_command_async(self,
                                          angles: List[MoveAnglesCommandParamsAngleInfo],
                                          timeout_seconds: float = 60.0,
                                          throw_error: bool = True,
                                          enable_feedback: bool = False,
                                          velocity_factor: float = 0.1,
                                          acceleration_factor: float = 0.1) -> MoveAnglesCommand:
        self.move_angles_command = MoveAnglesCommand(self.message_bus.publish,
                                                     angles,
                                                     timeout_seconds,
                                                     throw_error,
                                                     velocity_factor,
                                                     acceleration_factor,
                                                     self.message_bus,
                                                     enable_feedback)
        self.message_bus.subscribe(COMMAND_FEEDBACK_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.active_commands[self.move_angles_command.command_id] = self.move_angles_command
        if enable_feedback:
            self.specific_command.promise.add_feedback_callback(self._on_run_feedback)
        return self.move_angles_command

    async def _run_move_to_angles_command_async_await(self,
                                                      angles: List[MoveAnglesCommandParamsAngleInfo],
                                                      timeout_seconds: float = 60.0,
                                                      throw_error: bool = True,
                                                      velocity_factor: float = 0.1,
                                                      acceleration_factor: float = 0.1) -> None:
        await self._run_async(
            self._run_move_to_angles_command,
            angles,
            timeout_seconds,
            throw_error,
            velocity_factor=velocity_factor, acceleration_factor=acceleration_factor
        )

    def _run_move_to_angles_command(self, angles: List[MoveAnglesCommandParamsAngleInfo], timeout_seconds: float = 60.0,
                                    throw_error: bool = True,
                                    velocity_factor: float = 0.1,
                                    acceleration_factor: float = 0.1) -> None:
        command = self._run_move_to_angles_command_async(angles, timeout_seconds, throw_error,
                                                         velocity_factor=velocity_factor,
                                                         acceleration_factor=acceleration_factor)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.move_angles_command = None

    def get_cartesian_coordinates_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> Promise:
        self.cartesian_coordinates_promise = Promise(timeout_seconds, throw_error)
        self.message_bus.subscribe(CARTESIAN_COORDINATES_TOPIC)
        return self.cartesian_coordinates_promise

    async def get_cartesian_coordinates_async_await(self, timeout_seconds: float = 60.0,
                                                    throw_error: bool = True) -> str:
        return await self._run_async(self.get_cartesian_coordinates, timeout_seconds, throw_error)

    def get_cartesian_coordinates(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> str:
        promise = self.get_cartesian_coordinates_async(timeout_seconds, throw_error)
        promise.result()
        try:
            return self.last_cartesian_coordinates
        finally:
            self.cartesian_coordinates_promise = None

    def get_joint_state_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> Promise:
        self.joint_state_promise = Promise(timeout_seconds, throw_error)
        self.message_bus.subscribe(JOINT_INFO_TOPIC)
        return self.joint_state_promise

    async def get_joint_state_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> str:
        return await self._run_async(self.get_joint_state, timeout_seconds, throw_error)

    def get_joint_state(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> str:
        promise = self.get_joint_state_async(timeout_seconds, throw_error)
        promise.result()
        try:
            return self.last_joint_state
        finally:
            self.joint_state_promise = None

    def set_state_async(self, state_id: int, timeout_seconds: float = 6.0, throw_error: bool = True) -> SetStateCommand:
        """Асинхронно устанавливает состояние манипулятора по docs_api."""
        self.specific_command = SetStateCommand(
            state_id,
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.active_commands[self.specific_command.command_id] = self.specific_command
        return self.specific_command

    async def set_state_async_await(self, state_id: int, timeout_seconds: float = 6.0,
                                    throw_error: bool = True) -> None:
        await self._run_async(self.set_state, state_id, timeout_seconds, throw_error)

    def set_state(self, state_id: int, timeout_seconds: float = 6.0, throw_error: bool = True) -> None:
        command = self.set_state_async(state_id, timeout_seconds, throw_error)
        command.make_command_action()
        try:
            command.result()
        finally:
            self.specific_command = None

    def change_state_async(self, state: ManipulatorState, timeout_seconds: float = 6.0, throw_error: bool = True):
        return self.set_state_async(state.value, timeout_seconds, throw_error)

    async def change_state_async_await(self, state: ManipulatorState, timeout_seconds: float = 6.0,
                                       throw_error: bool = True) -> None:
        await self._run_async(self.change_state, state, timeout_seconds, throw_error)

    def change_state(self, state: ManipulatorState, timeout_seconds: float = 6.0, throw_error: bool = True) -> None:
        self.set_state(state.value, timeout_seconds, throw_error)

    def run_program_json_async(self, name: str, program_json: dict, timeout_seconds: float = 60.0,
                               throw_error: bool = True, enable_feedback: bool = False) -> RunProgramJsonCommand:
        self.specific_command = RunProgramJsonCommand(
            name,
            program_json,
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
            enable_feedback
        )
        self.message_bus.subscribe(COMMAND_FEEDBACK_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        if enable_feedback:
            self.specific_command.promise.add_feedback_callback(self._on_run_feedback)
        return self.specific_command

    async def run_program_json_async_await(self, name: str, program_json: dict, timeout_seconds: float = 60.0,
                                           throw_error: bool = True) -> None:
        await self._run_async(self.run_program_json, name, program_json, timeout_seconds, throw_error)

    def run_program_json(self, name: str, program_json: dict, timeout_seconds: float = 60.0,
                         throw_error: bool = True) -> None:
        command = self.run_program_json_async(name, program_json, timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        try:
            command.result()
        finally:
            self.specific_command = None

    def run_program_by_name_async(self, program_name: str, timeout_seconds: float = 60.0, throw_error: bool = True,
                                  enable_feedback: bool = False) -> RunProgramByNameCommand:
        self.specific_command = RunProgramByNameCommand(
            program_name,
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_FEEDBACK_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        if enable_feedback:
            self.specific_command.promise.add_feedback_callback(self._on_run_feedback)
        return self.specific_command

    async def run_program_by_name_async_await(self, program_name: str, timeout_seconds: float = 60.0,
                                              throw_error: bool = True) -> None:
        await self._run_async(self.run_program_by_name, program_name, timeout_seconds, throw_error)

    def run_program_by_name(self, program_name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.run_program_by_name_async(program_name, timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        try:
            command.result()
        finally:
            self.specific_command = None

    def run_python_program_async(self,
                                 python_code: str,
                                 env_name: str = "",
                                 python_version: str = "3.12",
                                 requirements: List[str] = None,
                                 timeout_seconds: float = 60.0,
                                 throw_error: bool = True,
                                 enable_feedback: bool = False) -> RunPythonProgramCommand:
        self.specific_command = RunPythonProgramCommand(
            python_code,
            self.message_bus.publish,
            env_name,
            python_version,
            requirements,
            timeout_seconds,
            throw_error,
            self.message_bus,
            enable_feedback
        )
        self.message_bus.subscribe(COMMAND_FEEDBACK_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def run_python_program_async_await(self,
                                             python_code: str,
                                             env_name: str = "",
                                             python_version: str = "3.12",
                                             requirements: List[str] = None,
                                             timeout_seconds: float = 60.0,
                                             throw_error: bool = True) -> None:
        await self._run_async(
            self.run_python_program,
            python_code,
            env_name,
            python_version,
            requirements,
            timeout_seconds,
            throw_error,
        )

    def run_python_program(self,
                           python_code: str,
                           env_name: str = "",
                           python_version: str = "3.12",
                           requirements: List[str] = None,
                           timeout_seconds: float = 60.0,
                           throw_error: bool = True) -> None:
        command = self.run_python_program_async(python_code, env_name, python_version, requirements, timeout_seconds,
                                                throw_error)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.specific_command = None

    def stop_movement_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> StopMovementCommand:
        self.specific_command = StopMovementCommand(
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def stop_movement_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.stop_movement, timeout_seconds, throw_error)

    def stop_movement(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.stop_movement_async(timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.specific_command = None

    def set_zero_z_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> SetZeroZCommand:
        self.specific_command = SetZeroZCommand(
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def set_zero_z_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.set_zero_z, timeout_seconds, throw_error)

    def set_zero_z(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.set_zero_z_async(timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.specific_command = None

    def tcp_add_async(self, name: str, position: Point3D, apply: bool, timeout_seconds: float = 60.0,
                      throw_error: bool = True) -> TCPAdd:
        self.specific_command = TCPAdd(
            name,
            position,
            apply,
            self.message_bus.publish,
            timeout_seconds,
            throw_error
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def tcp_add_async_wait(self, name: str, position: Point3D, apply: bool, timeout_seconds: float = 60.0,
                                 throw_error: bool = True):
        await self._run_async(self.tcp_add_async, name, position, apply, timeout_seconds, throw_error)

    def tcp_add(self, name: str, position: Point3D, apply: bool, timeout_seconds: float = 60.0,
                throw_error: bool = True) -> None:
        command = self.tcp_add_async(name, position, apply, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def write_analog_output_async(self, channel: int, value: float, timeout_seconds: float = 60.0,
                                  throw_error: bool = True) -> WriteAnalogOutputCommand:
        self.specific_command = WriteAnalogOutputCommand(
            channel,
            value,
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def write_analog_output_async_await(self, channel: int, value: float, timeout_seconds: float = 60.0,
                                              throw_error: bool = True) -> None:
        await self._run_async(self.write_analog_output, channel, value, timeout_seconds, throw_error)

    def write_analog_output(self, channel: int, value: float, timeout_seconds: float = 60.0,
                            throw_error: bool = True) -> None:
        command = self.write_analog_output_async(channel, value, timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.specific_command = None

    def write_gpio_async(self, name: str, value: int, timeout_seconds: float = 60.0,
                         throw_error: bool = True) -> WriteGPIO:
        self.specific_command = WriteGPIO(name, value, self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def write_gpio_async_await(self, name: str, value: int, timeout_seconds: float = 60.0,
                                     throw_error: bool = True) -> None:
        await self._run_async(self.write_gpio_async, name, value, timeout_seconds, throw_error)

    def write_gpio(self, name: str, value: int, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.write_gpio_async(name, value, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def tcp_delete_async(self, name: str, reset_current: bool = True, apply_other: str = "",
                         timeout_seconds: float = 60.0, throw_error: bool = True) -> TCPDelete:
        self.specific_command = TCPDelete(
            name,
            self.message_bus.publish,
            reset_current,
            apply_other,
            timeout_seconds,
            throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def tcp_delete_async_wait(self, name: str, reset_current: bool = True, apply_other: str = "",
                                    timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.tcp_delete_async, name, reset_current, apply_other, timeout_seconds, throw_error)

    def tcp_delete(self, name: str, reset_current: bool = True, apply_other: str = "", timeout_seconds: float = 60.0,
                   throw_error: bool = True) -> None:
        command = self.tcp_delete_async(name, reset_current, apply_other, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def tcp_apply_async(self, name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> TCPApply:
        self.specific_command = TCPApply(name, self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def tcp_apply_async_await(self, name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.tcp_apply_async, name, timeout_seconds, throw_error)

    def tcp_apply(self, name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.tcp_apply_async(name, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def tcp_get_current_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> TCPGetCurrent:
        self.specific_command = TCPGetCurrent(self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    def tcp_get_current(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> Dict[str, Any]:
        command = self.tcp_get_current_async(timeout_seconds, throw_error)
        command.make_command_action()
        return command.result()

    def tcp_get_list_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> TCPGetList:
        self.specific_command = TCPGetList(self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    def tcp_get_list(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> Dict[str, Any]:
        command = self.tcp_get_list_async(timeout_seconds, throw_error)
        command.make_command_action()
        return command.result()

    def write_i2c_async(self, name: str, value: int, timeout_seconds: float = 60.0,
                        throw_error: bool = True) -> WriteI2C:
        self.specific_command = WriteI2C(name, value, self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def write_i2c_async_await(self, name: str, value: int, timeout_seconds: float = 60.0,
                                    throw_error: bool = True) -> None:
        await self._run_async(self.write_i2c_async, name, value, timeout_seconds, throw_error)

    def write_i2c(self, name: str, value: int, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.write_i2c_async(name, value, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def write_digital_output_async(self, channel: int, value: bool, timeout_seconds: float = 60.0,
                                   throw_error: bool = True) -> WriteDigitalOutputCommand:
        self.specific_command = WriteDigitalOutputCommand(
            channel,
            value,
            self.message_bus.publish,
            timeout_seconds,
            throw_error,
            self.message_bus,
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def write_digital_output_async_await(self, channel: int, value: bool, timeout_seconds: float = 60.0,
                                               throw_error: bool = True) -> None:
        await self._run_async(self.write_digital_output, channel, value, timeout_seconds, throw_error)

    def write_digital_output(self, channel: int, value: bool, timeout_seconds: float = 60.0,
                             throw_error: bool = True) -> None:
        command = self.write_digital_output_async(channel, value, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def set_joint_limits_async(self, limits: list[JointLimit], timeout_seconds: float = 60.0,
                               throw_error: bool = True) -> SetJointLimits:
        self.specific_command = SetJointLimits(limits, self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def set_joint_limits_async_await(self, limits: list[JointLimit], timeout_seconds: float = 60.0,
                                           throw_error: bool = True) -> None:
        await self._run_async(self.set_joint_limits, limits, timeout_seconds, throw_error)

    def set_joint_limits(self, limits: list[JointLimit], timeout_seconds: float = 60.0,
                         throw_error: bool = True) -> None:
        command = self.set_joint_limits_async(limits, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def get_joint_limits_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> GetJointLimits:
        self.specific_command = GetJointLimits(self.message_bus.publish, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def get_joint_limits_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.get_joint_limits, timeout_seconds, throw_error)

    def get_joint_limits(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.get_joint_limits_async(timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def move_group_async(self, move_type: MoveType, points: list[Union[Point, Pose]], timeout_seconds: float = 60.0,
                         throw_error: bool = True) -> SdkCommand:
        self.specific_command = MoveGroup(move_type, points)
        for point in self.specific_command.points:
            if isinstance(move_type, MoveType.JOINT):
                return self._run_move_to_angles_command_async(point.positions, timeout_seconds, throw_error)
            if isinstance(move_type, MoveType.POINT_TO_POINT):
                position = MoveCoordinatesParamsPosition(point.position.x, point.position.y, point.position.z)
                orientation = MoveCoordinatesParamsOrientation(point.orientation.x, point.orientation.y,
                                                               point.orientation.z, point.orientation.w)
                return self.move_to_coordinates_async(position, orientation, point.velocity_factor,
                                                      point.acceleration_factor, PlannerType.PTP, timeout_seconds,
                                                      throw_error)
            if isinstance(move_type, MoveType.LINE):
                position = MoveCoordinatesParamsPosition(point.position.x, point.position.y, point.position.z)
                orientation = MoveCoordinatesParamsOrientation(point.orientation.x, point.orientation.y,
                                                               point.orientation.z, point.orientation.w)
                return self.move_to_coordinates_async(position, orientation, point.velocity_factor,
                                                      point.acceleration_factor, PlannerType.LIN, timeout_seconds,
                                                      throw_error)
            if isinstance(move_type, MoveType.ARC):
                pass
        return None

    async def move_group_async_await(self, move_type: MoveType, points: list[Union[Point, Pose]],
                                     timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.move_group, move_type, points, timeout_seconds, throw_error)

    def move_group(self, move_type: MoveType, points: list[Union[Point, Pose]], timeout_seconds: float = 60.0,
                   throw_error: bool = True):
        command = self.get_joint_limits_async(timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def arc_motion_async(self,
                         target: Pose,
                         center_arc: Pose,
                         step: float = 0.05,
                         count_point_arc: int = 50,
                         max_velocity_scaling_factor: float = 0.5,
                         max_acceleration_scaling_factor: float = 0.5,
                         timeout_seconds: float = 60.0,
                         throw_error: bool = True,
                         enable_feedback: bool = False) -> ArcMotion:
        self.specific_command = ArcMotion(target=target,
                                          center_arc=center_arc,
                                          step=step,
                                          count_point_arc=count_point_arc,
                                          max_velocity_scaling_factor=max_velocity_scaling_factor,
                                          max_acceleration_scaling_factor=max_acceleration_scaling_factor,
                                          send_command=self.message_bus.publish,
                                          timeout_seconds=timeout_seconds,
                                          throw_error=throw_error,
                                          enable_feedback=enable_feedback)
        self.message_bus.subscribe(COMMAND_FEEDBACK_TOPIC)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)

        if enable_feedback:
            self.specific_command.promise.add_feedback_callback(self._on_run_feedback)
        return self.specific_command

    async def arc_motion_async_await(self,
                                     target: Pose,
                                     center_arc: Pose,
                                     step: float = 0.05,
                                     count_point_arc: int = 50,
                                     max_velocity_scaling_factor: float = 0.5,
                                     max_acceleration_scaling_factor: float = 0.5,
                                     timeout_seconds: float = 60.0,
                                     throw_error: bool = True) -> None:
        await self._run_async(self.arc_motion,
                              target,
                              center_arc,
                              step,
                              count_point_arc,
                              max_velocity_scaling_factor,
                              max_acceleration_scaling_factor,
                              timeout_seconds,
                              throw_error)

    def arc_motion(self,
                   target: Pose,
                   center_arc: Pose,
                   step: float = 0.05,
                   count_point_arc: int = 50,
                   max_velocity_scaling_factor: float = 0.5,
                   max_acceleration_scaling_factor: float = 0.5,
                   timeout_seconds: float = 60.0,
                   throw_error: bool = True) -> None:
        command = self.arc_motion_async(target=target,
                                        center_arc=center_arc,
                                        step=step,
                                        count_point_arc=count_point_arc,
                                        max_velocity_scaling_factor=max_velocity_scaling_factor,
                                        max_acceleration_scaling_factor=max_acceleration_scaling_factor,
                                        timeout_seconds=timeout_seconds,
                                        throw_error=throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    # Методы для потокового управления
    def stream_joint_positions(self, positions: Dict[str, float], velocities: Dict[str, float]) -> None:
        """
        Стриминг позиций суставов манипулятора
        :param positions: Словарь позиций, где ключ - имя, значение - позиция в радианах
        :param velocities: Словарь скоростей, где ключ - имя, значение - скорость в рад/с
        """
        message = {
            "stream": "joint",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "positions": positions,
                "velocities": velocities
            }
        }

        self.message_bus.publish("/stream", message)

    def stream_coordinates(self, position: MoveCoordinatesParamsPosition,
                           orientation: MoveCoordinatesParamsOrientation) -> None:
        """
        :param position: Позиция манипулятора (x, y, z)
        :param orientation: Ориентация манипулятора (x, y, z, w)
        """
        message = {
            "stream": "pose",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "position": position.__dict__,
                "orientation": orientation.__dict__
            }
        }
        self.message_bus.publish("/stream", message)

    def stream_cartesian_velocities(self, linear_velocities: Dict[str, float],
                                    angular_velocities: Dict[str, float]) -> None:
        """
        :param linear_velocities: Словарь линейных скоростей по осям, например {"x": 0.1, "y": 0.0, "z": 0.0}
        :param angular_velocities: Словарь угловых скоростей по осям, например {"rx": 0.0, "ry": 0.0, "rz": 0.1}
        """
        # Преобразуем angular_velocities в правильный формат (rx, ry, rz -> x, y, z)
        angular_converted = {
            "x": angular_velocities.get("rx", 0.0),
            "y": angular_velocities.get("ry", 0.0),
            "z": angular_velocities.get("rz", 0.0)
        }

        message = {
            "stream": "twist",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "linear": linear_velocities,
                "angular": angular_converted
            }
        }
        self.message_bus.publish("/stream", message)

    # Асинхронные версии методов потокового управления
    async def stream_coordinates_async(self, position: MoveCoordinatesParamsPosition,
                                       orientation: MoveCoordinatesParamsOrientation) -> None:
        """
        :param position: Позиция манипулятора (x, y, z)
        :param orientation: Ориентация манипулятора (x, y, z, w)
        """
        message = {
            "stream": "pose",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "position": position.__dict__,
                "orientation": orientation.__dict__
            }
        }
        self.message_bus.publish("/stream", message)

    async def stream_cartesian_velocities_async(self, linear_velocities: Dict[str, float],
                                                angular_velocities: Dict[str, float]) -> None:
        """
        :param linear_velocities: Словарь линейных скоростей по осям, например {"x": 0.1, "y": 0.0, "z": 0.0}
        :param angular_velocities: Словарь угловых скоростей по осям, например {"rx": 0.0, "ry": 0.0, "rz": 0.1}
        """
        # Преобразуем angular_velocities в правильный формат (rx, ry, rz -> x, y, z)
        angular_converted = {
            "x": angular_velocities.get("rx", 0.0),
            "y": angular_velocities.get("ry", 0.0),
            "z": angular_velocities.get("rz", 0.0)
        }

        message = {
            "stream": "twist",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "linear": linear_velocities,
                "angular": angular_converted
            }
        }
        self.message_bus.publish("/stream", message)

    async def stream_joint_positions_async(self, positions: Dict[str, float], velocities: Dict[str, float]) -> None:
        """
        Асинхронный стриминг позиций суставов манипулятора

        :param positions: Словарь позиций, где ключ - имя, значение - позиция в радианах
        :param velocities: Словарь скоростей, где ключ - имя, значение - скорость в рад/с
        """
        message = {
            "stream": "joint",
            "data": {
                "header": {
                    "stamp": "now",
                    "frame_id": "base_link"
                },
                "positions": positions,
                "velocities": velocities
            }
        }

        self.message_bus.publish("/stream", message)

    # Методы для управления режимом MoveIt Servo
    def set_servo_control_type_async(self, control_type: ServoControlType, timeout_seconds: float = 60.0,
                                     throw_error: bool = True) -> ServoControlTypeCommand:
        """
        Асинхронно устанавливает тип управления сервоприводом.

        :param control_type: Тип управления (из перечисления ServoControlType).
        :param timeout_seconds: Таймаут ожидания ответа.
        :param throw_error: Выбрасывать ли исключение при ошибке.
        :return: Promise, который будет разрешен с результатом команды.
        """
        self.specific_command = ServoControlTypeCommand(
            send_command=self.message_bus.publish,
            control_type_id=control_type.value,
            timeout_seconds=timeout_seconds,
            throw_error=throw_error,
            message_bus=self.message_bus
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def set_servo_control_type_async_await(self, control_type: ServoControlType, timeout_seconds: float = 60.0,
                                                 throw_error: bool = True) -> None:
        await self._run_async(self.set_servo_control_type, control_type, timeout_seconds, throw_error)

    def set_servo_control_type(self, control_type: ServoControlType, timeout_seconds: float = 60.0,
                               throw_error: bool = True) -> None:
        """
        Устанавливает тип управления сервоприводом.

        :param control_type: Тип управления (из перечисления ServoControlType).
        :param timeout_seconds: Таймаут ожидания ответа.
        :param throw_error: Выбрасывать ли исключение при ошибке.
        """
        command = self.set_servo_control_type_async(control_type, timeout_seconds, throw_error)
        command.make_command_action()  # Отправляем команду
        command.result()
        self.specific_command = None

    def set_servo_joint_jog_mode(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        """
        Установка режима JOINT_JOG для MoveIt Servo
        :param timeout_seconds: Таймаут выполнения команды
        :param throw_error: исключение при ошибке
        """
        self.set_servo_control_type(ServoControlType.JOINT_JOG, timeout_seconds, throw_error)

    def set_servo_twist_mode(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        """
        Установить режим управления сервоприводом TWIST
        :param timeout_seconds: Timeout операции (по умолчанию 60 секунд)
        :param throw_error: Флаг выбрасывания исключения при ошибке (True - выбрасывать исключение, False - возвращать объект с ошибкой)
        """
        self.set_servo_control_type(ServoControlType.TWIST, timeout_seconds, throw_error)

    def set_servo_pose_mode(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        """
        Установить режим управления сервоприводом POSE
        :param timeout_seconds: Timeout операции (по умолчанию 60 секунд)
        :param throw_error: Флаг выбрасывания исключения при ошибке (True - выбрасывать исключение, False - возвращать объект с ошибкой)
        """
        self.set_servo_control_type(ServoControlType.POSE, timeout_seconds, throw_error)

    def enable_servo_streaming(self, enabled: bool = True, timeout_seconds: float = 60.0,
                               throw_error: bool = True) -> None:
        """
        Включает/выключает потоковую передачу данных для серво-режима.

        :param enabled: Включить (True) или выключить (False) потоковую передачу данных.
        :param timeout_seconds: Таймаут ожидания ответа.
        :param throw_error: Выбрасывать ли исключение при ошибке.
        """
        self.specific_command = ServoControlTypeCommand(
            self.message_bus.publish,
            ServoControlType.TWIST.value if enabled else ServoControlType.JOINT_JOG.value,
            timeout_seconds,
            throw_error,
            self.message_bus
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.specific_command.make_command_action()
        try:
            self.specific_command.result()
        finally:
            self.specific_command = None

    async def enable_servo_streaming_async(self, enabled: bool = True, timeout_seconds: float = 60.0,
                                           throw_error: bool = True) -> None:
        """
        Асинхронно включает/выключает потоковую передачу данных для серво-режима.

        :param enabled: Включить (True) или выключить (False) потоковую передачу данных.
        :param timeout_seconds: Таймаут ожидания ответа.
        :param throw_error: Выбрасывать ли исключение при ошибке.
        """
        await self._run_async(self.enable_servo_streaming, enabled, timeout_seconds, throw_error)

    # Методы без ожидания результата
    def change_state_no_wait(self, state: ManipulatorState) -> None:
        """
        Изменяет состояние манипулятора без ожидания ответа.

        :param state: Новое состояние (из перечисления ManipulatorState).
        """

        command = NoWaitCommand(self.message_bus.publish, "set_state", {"id": state.value},
                                message_bus=self.message_bus)
        command.make_command_action()

    def run_program_json_no_wait(self, name: str, program_json: dict) -> None:
        """
        Запускает JSON-программу без ожидания ответа.

        :param name: Имя программы.
        :param program_json: JSON с описанием программы.
        """

        command = NoWaitCommand(self.message_bus.publish, "play_program_json", {"name": name, "json": program_json},
                                message_bus=self.message_bus)
        command.make_command_action()

    def run_program_by_name_no_wait(self, program_name: str) -> None:
        """
        Запускает программу по имени без ожидания ответа.

        :param program_name: Имя программы.
        """

        command = NoWaitCommand(self.message_bus.publish, "play_program_name", {"name": program_name},
                                message_bus=self.message_bus)
        command.make_command_action()

    def run_python_program_no_wait(self,
                                   python_code: str,
                                   env_name: str = "",
                                   python_version: str = "3.12",
                                   requirements: List[str] = None) -> None:
        """
        Запускает Python-программу без ожидания ответа.

        :param python_code: Код Python.
        :param env_name: Имя окружения.
        :param python_version: Версия Python.
        :param requirements: Список требований.
        """

        data = {
            "code": python_code,
            "env_name": env_name,
            "python_version": python_version,
            "requirements": requirements or []
        }
        command = NoWaitCommand(self.message_bus.publish, "execute_python_code", data, message_bus=self.message_bus)
        command.make_command_action()

    def stop_movement_no_wait(self) -> None:
        """
        Останавливает движение манипулятора без ожидания ответа.
        """

        command = NoWaitCommand(self.message_bus.publish, "stop_moving", {}, message_bus=self.message_bus)
        command.make_command_action()

    def set_zero_z_no_wait(self) -> None:
        """
        Устанавливает нулевую точку по оси Z без ожидания ответа.
        """

        command = NoWaitCommand(self.message_bus.publish, "set_zero", {"tf_name": "tool1"},
                                message_bus=self.message_bus)
        command.make_command_action()

    def write_analog_output_no_wait(self, channel: int, value: float) -> None:
        """
        Записывает значение в аналоговый выход без ожидания ответа.

        :param channel: Номер канала.
        :param value: Значение (0.0 - 1.0).
        """

        command = NoWaitCommand(self.message_bus.publish, "write_analog_output", {"channel": channel, "value": value},
                                message_bus=self.message_bus)
        command.make_command_action()

    def write_digital_output_no_wait(self, channel: int, value: bool) -> None:
        """
        Записывает значение в цифровой выход без ожидания ответа.

        :param channel: Номер канала.
        :param value: Значение (True/False).
        """

        command = NoWaitCommand(self.message_bus.publish, "write_digital_output", {"channel": channel, "value": value},
                                message_bus=self.message_bus)
        command.make_command_action()

    def move_to_coordinates_no_wait(self,
                                    position: MoveCoordinatesParamsPosition,
                                    orientation: MoveCoordinatesParamsOrientation,
                                    velocity_scaling_factor: float,
                                    acceleration_scaling_factor: float) -> None:
        """
        Перемещает манипулятор в заданные координаты без ожидания ответа.

        :param position: Позиция (x, y, z).
        :param orientation: Ориентация (x, y, z, w).
        :param velocity_scaling_factor: Множитель скорости (0.0 - 1.0).
        :param acceleration_scaling_factor: Множитель ускорения (0.0 - 1.0).
        """

        data = {
            "position": {
                "x": position.x,
                "y": position.y,
                "z": position.z
            },
            "orientation": {
                "x": orientation.x,
                "y": orientation.y,
                "z": orientation.z,
                "w": orientation.w
            },
            "velocity_factor": velocity_scaling_factor,
            "acceleration_factor": acceleration_scaling_factor
        }
        command = NoWaitCommand(self.message_bus.publish, "set_coordinates", data, message_bus=self.message_bus)
        self.active_commands[command.command_id] = command
        command.make_command_action()

    def _run_move_to_angles_command_no_wait(self, angles: List[MoveAnglesCommandParamsAngleInfo],
                                            velocity_factor: float = 0.1, acceleration_factor: float = 0.1) -> None:
        """
        Выполняет команду перемещения по углам без ожидания ответа.

        :param angles: Список информации об углах.
        """

        positions = {}
        velocities = {}

        for angle in angles:
            positions[angle.name] = angle.position
            velocities[angle.name] = angle.velocity

        data = {
            "positions": positions,
            "velocities": velocities,
            "velocity_factor": velocity_factor,
            "acceleration_factor": acceleration_factor
        }

        command = NoWaitCommand(self.message_bus.publish, "move_joints", data, message_bus=self.message_bus)
        self.active_commands[command.command_id] = command
        command.make_command_action()

    def set_servo_control_type_no_wait(self, control_type: ServoControlType) -> None:
        """
        Устанавливает тип управления сервоприводом без ожидания ответа.

        :param control_type: Тип управления (из перечисления ServoControlType).
        """
        command = NoWaitCommand(self.message_bus.publish, "servo_control_type", {"id": control_type.value},
                                message_bus=self.message_bus)
        command.make_command_action()

    def set_servo_joint_jog_mode_no_wait(self) -> None:
        """
        Устанавливает режим JOINT_JOG без ожидания ответа.
        """
        self.set_servo_control_type_no_wait(ServoControlType.JOINT_JOG)

    def set_servo_twist_mode_no_wait(self) -> None:
        """
        Устанавливает режим TWIST без ожидания ответа.
        """
        self.set_servo_control_type_no_wait(ServoControlType.TWIST)

    def set_servo_pose_mode_no_wait(self) -> None:
        """
        Устанавливает режим POSE без ожидания ответа.
        """
        self.set_servo_control_type_no_wait(ServoControlType.POSE)

    def get_control_no_wait(self) -> None:
        """
        Получает возможность управления манипулятором без ожидания ответа.
        """
        # Отправляем команду напрямую в правильный топик /management как в обычном методе
        self.message_bus.publish("/management", {
            "get_management": True
        })

    def play_audio(self, file_name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.play_audio_async(file_name, timeout_seconds, throw_error)
        command.result()
        self.specific_command = None

    def play_audio_async(self, file_name: str, timeout_seconds: float = 60.0,
                         throw_error: bool = True) -> PlayAudioCommand:
        self.specific_command = PlayAudioCommand(self.message_bus.publish, file_name, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.specific_command.make_command_action()
        return self.specific_command

    async def play_audio_async_await(self, file_name: str, timeout_seconds: float = 60.0,
                                     throw_error: bool = True) -> None:
        cmd = self.play_audio_async(file_name, timeout_seconds, throw_error)
        await cmd.async_result()
        self.specific_command = None

    # -------------------------------------------------
    # Публичный API для событий
    # -------------------------------------------------

    def topic_listener(self, topic: str):
        """Декоратор: вызовет функцию один раз при получении сообщения из *topic* и вернёт его результат.

        Пример:
            @robot.topic_listener("/coordinates")
            async def handle_coords(msg):
                print(msg)
        """

        def decorator(func):
            async def wrapper(*args, **kwargs):
                from sdk.promise import Promise  # локальный импорт чтобы избежать циклов

                promise = Promise()

                # Подписываемся на сообщения выбранного топика через собственный обработчик
                previous_handler = self.on_message  # может быть None
                # Подписываемся на топик на уровне MQTT
                try:
                    self.message_bus.subscribe(topic)
                except Exception:
                    pass

                def _combined_handler(t: str, msg: str):
                    # Если нужный топик – резолвим promise
                    if t == topic:
                        promise.resolve(msg)
                    # Передаём дальше
                    if previous_handler is not None:
                        previous_handler(t, msg)

                # Назначаем временный обработчик
                self.on_message = _combined_handler

                try:
                    payload = await promise.async_result()
                finally:
                    # Возвращаем предыдущий обработчик
                    self.on_message = previous_handler
                    try:
                        self.message_bus.unsubscribe(topic)
                    except Exception:
                        pass

                # вызываем оригинальный обработчик
                return await func(payload, *args, **kwargs)

            return wrapper

        return decorator

    # Свойство on_message: позволяет назначить единый обработчик всех входящих сообщений

    @property
    def on_message(self):
        return self._user_message_handler

    @on_message.setter
    def on_message(self, handler: Callable[[str, str], None]):
        if not callable(handler):
            raise TypeError("Обработчик должен быть вызываемым объектом (функцией или методом)")
        self._user_message_handler = handler

    # --- Обработчики событий ---

    def _set_topic_handler(self, topic: str, handler: Callable[[Dict[str, Any]], None]):
        """
        Вспомогательный метод для подписки на топик и установки обработчика.
        """
        if not callable(handler):
            raise TypeError("Обработчик должен быть функцией или методом")
        self.message_bus.subscribe(topic)
        self._topic_handlers[topic] = handler

    def set_coordinates_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/coordinates", handler)

    def set_joint_states_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/joint_states", handler)

    def set_gpio_states_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/gpio_states", handler)

    def set_gamepad_info_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/gamepad_info", handler)

    def set_hardware_state_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/hardware_state", handler)

    def set_coordinate_limits_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/coordinate_limits", handler)

    def set_hardware_error_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/hardware_error", handler)

    def set_manipulator_info_handler(self, handler: Callable[[Dict[str, Any]], None]) -> None:
        self._set_topic_handler("/manipulator_info", handler)

    # --- Декораторы для обработчиков событий ---

    def on_topic(self, topic: str):
        """
        Фабрика декораторов для подписки на события из определенного топика.
        """

        def decorator(handler: Callable[[Dict[str, Any]], None]):
            self._set_topic_handler(topic, handler)
            return handler

        return decorator

    def on_coordinates(self):
        return self.on_topic("/coordinates")

    def on_joint_states(self):
        return self.on_topic("/joint_states")

    def on_gpio_states(self):
        return self.on_topic("/gpio_states")

    def on_gamepad_info(self):
        return self.on_topic("/gamepad_info")

    def on_hardware_state(self):
        return self.on_topic("/hardware_state")

    def on_coordinate_limits(self):
        return self.on_topic("/coordinate_limits")

    def on_hardware_error(self):
        return self.on_topic("/hardware_error")

    def on_manipulator_info(self):
        return self.on_topic("/manipulator_info")

    def clear_all_commands(self) -> None:
        """Принудительно очищает все незавершенные команды"""
        print(f"[MANIPULATOR] Принудительная очистка всех команд")

        # Очищаем активные команды MEdu (новая схема)
        if hasattr(self, 'active_commands') and self.active_commands:
            print(f"[MANIPULATOR] Очищаем active_commands: {list(self.active_commands.keys())}")
            for cmd_id, command in self.active_commands.items():
                print(f"[MANIPULATOR] Очищаем активную команду ID={cmd_id}, тип: {type(command).__name__}")
            self.active_commands.clear()

        # Очищаем команды старой схемы
        if self.specific_command is not None:
            print(
                f"[MANIPULATOR] Очищаем specific_command: {type(self.specific_command).__name__} ID={self.specific_command.command_id}")
        if self.move_coordinates_command is not None:
            print(f"[MANIPULATOR] Очищаем move_coordinates_command: ID={self.move_coordinates_command.command_id}")
        if self.move_angles_command is not None:
            print(f"[MANIPULATOR] Очищаем move_angles_command: ID={self.move_angles_command.command_id}")
        if self.manage_command is not None:
            print(f"[MANIPULATOR] Очищаем manage_command: ID={self.manage_command.command_id}")

        self.specific_command = None
        self.move_coordinates_command = None
        self.move_angles_command = None
        self.manage_command = None

        self.cartesian_coordinates_promise = None
        self.joint_state_promise = None

        print(f"[MANIPULATOR] Все команды очищены")

    def disconnect(self) -> None:
        """Разрывает соединение с шиной сообщений и останавливает внутренние потоки MQTT.

        Метод безопасен к повторному вызову: если соединение уже разорвано, он ничего не делает.
        """
        try:
            if self.message_bus is not None and getattr(self.message_bus, "is_connected", False):
                self.message_bus.disconnect()
        except Exception as e:
            # Предпочитаем не выбрасывать исключение при финализации, выводим отладочную информацию
            print(f"[MANIPULATOR] Ошибка при отключении: {e}")

    def __del__(self):
        """Гарантируем остановку MQTT-треда при сборке GC."""
        try:
            self.disconnect()
        except Exception:
            # Никогда не бросаем исключения из деструктора
            pass

    def unsubscribe_from_topic(self, topic: str) -> None:
        """Отписывается от конкретного топика и удаляет связанный обработчик.

        Args:
            topic: Топик, от которого нужно отписаться (например, "/joint_states")
        """
        try:
            # Отписываемся на уровне MQTT
            self.message_bus.unsubscribe(topic)

            # Удаляем обработчик из словаря
            if topic in self._topic_handlers:
                del self._topic_handlers[topic]
                print(f"[MANIPULATOR] Отписались от топика {topic}")
            else:
                print(f"[MANIPULATOR] Топик {topic} не имел зарегистрированного обработчика")
        except Exception as e:
            print(f"[MANIPULATOR] Ошибка при отписке от топика {topic}: {e}")

    def unsubscribe_from_streaming_topics(self) -> None:
        """Отписывается от всех потоковых топиков, которые могут генерировать частые сообщения."""
        streaming_topics = [
            "/joint_states",  # состояние суставов
            "/coordinates",  # текущие координаты
            "/hardware_state",  # состояние железа
            "/gpio_states",  # состояние GPIO
        ]

        print("[MANIPULATOR] Отписываемся от потоковых топиков...")
        for topic in streaming_topics:
            self.unsubscribe_from_topic(topic)
        print("[MANIPULATOR] Отписка от потоковых топиков завершена")

    def clear_all_handlers(self) -> None:
        """Удаляет все зарегистрированные обработчики событий, не затрагивая соединение."""
        print("[MANIPULATOR] Очищаем все обработчики событий...")

        # Очищаем пользовательский обработчик
        self._user_message_handler = None

        # Очищаем обработчики топиков
        for topic in list(self._topic_handlers.keys()):
            self.unsubscribe_from_topic(topic)

        print("[MANIPULATOR] Все обработчики событий очищены")

    def set_conveyer_velocity(self, velocity: float, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.set_conveyer_velocity_async(velocity, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def set_conveyer_velocity_async(self, velocity: float, timeout_seconds: float = 60.0,
                                    throw_error: bool = True) -> SetConveyorVelocityCommand:
        self.specific_command = SetConveyorVelocityCommand(
            self.message_bus.publish,
            velocity,
            timeout_seconds,
            throw_error
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def set_conveyer_velocity_async_await(self, velocity: float, timeout_seconds: float = 60.0,
                                                throw_error: bool = True) -> None:
        await self._run_async(self.set_conveyer_velocity, velocity, timeout_seconds, throw_error)

    def calibrate_controller_async(self, timeout_seconds: float = 60.0,
                                   throw_error: bool = True) -> CalibrateControllerCommand:
        self.specific_command = CalibrateControllerCommand(
            self.message_bus.publish,
            timeout_seconds,
            throw_error
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def calibrate_controller_async_await(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        await self._run_async(self.calibrate_controller, timeout_seconds, throw_error)

    def calibrate_controller(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.calibrate_controller_async(timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def move_linear_module_async(self, distance: float, timeout_seconds: float = 60.0,
                                 throw_error: bool = True) -> MoveLinearModuleCommand:
        self.specific_command = MoveLinearModuleCommand(
            self.message_bus.publish,
            distance,
            timeout_seconds,
            throw_error
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def move_linear_module_async_await(self, distance: float, timeout_seconds: float = 60.0,
                                             throw_error: bool = True) -> None:
        await self._run_async(self.move_linear_module, distance, timeout_seconds, throw_error)

    def move_linear_module(self, distance: float, timeout_seconds: float = 60.0, throw_error: bool = True) -> None:
        command = self.move_linear_module_async(distance, timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        self.specific_command = None

    def get_block_coordinates_from_pixy_async(self, signature: int, timeout_seconds: float = 60.0,
                                              throw_error: bool = True) -> PixyCamGetCoordinatesCommand:
        self.specific_command = PixyCamGetCoordinatesCommand(
            self.message_bus.publish,
            signature,
            timeout_seconds,
            throw_error
        )
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        return self.specific_command

    async def get_block_coordinates_from_pixy_async_await(self, signature: int, timeout_seconds: float = 60.0,
                                                          throw_error: bool = True) -> None:
        return await self._run_async(self.get_block_coordinates_from_pixy, signature, timeout_seconds, throw_error)

    def get_block_coordinates_from_pixy(self, signature: int, timeout_seconds: float = 60.0,
                                        throw_error: bool = True) -> None:
        command = self.get_block_coordinates_from_pixy_async(signature, timeout_seconds, throw_error)
        promise = self.get_pixy_coordinates_async(timeout_seconds, throw_error)
        command.make_command_action()
        command.result()
        promise.result()
        self.specific_command = None
        try:
            return self.last_pixy_coordinates
        finally:
            self.pixy_coordinates_promise = None

    def get_pixy_coordinates_async(self, timeout_seconds: float = 60.0, throw_error: bool = True) -> Promise:
        self.pixy_coordinates_promise = Promise(timeout_seconds, throw_error)
        self.message_bus.subscribe(PIXY_CAM_COORDINATES_TOPIC)
        return self.pixy_coordinates_promise

    def get_gpio_value(self, name: str, timeout_seconds: float = 60.0, throw_error: bool = True) -> Optional[float]:
        self.specific_command = GetGpio(self.message_bus.publish, name, timeout_seconds, throw_error)
        self.message_bus.subscribe(COMMAND_TOPIC)
        self.message_bus.subscribe(COMMAND_RESULT_TOPIC)
        self.specific_command.make_command_action()
        result: dict[str, Any] = self.specific_command.result()
        self.specific_command = None
        return result.get('data', {}).get('value', None)
