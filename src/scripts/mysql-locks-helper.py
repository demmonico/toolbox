#!/usr/bin/env python3

import asyncio
import math
import signal
from typing import Any

import click
import mysql.connector
from prettytable import PrettyTable


class GracefulExit(Exception):
    def __init__(self, message: str = "") -> None:
        super().__init__(message)


async def dump_table(
    connection: mysql.connector.MySQLConnection,
    db_name: str,
    table_name: str,
) -> None:
    cur = connection.cursor()
    cur.execute(
        f"SELECT COLUMN_NAME FROM information_schema.columns WHERE TABLE_NAME = '{table_name}' and TABLE_SCHEMA='{db_name}'"
    )
    rows = cur.fetchall()

    fields = []

    for row in rows:
        fields.append(row[0])

    table = PrettyTable()

    table.field_names = fields

    cur.execute(f"SELECT {','.join(fields)} FROM `{db_name}`.`{table_name}`")
    rows = cur.fetchall()

    for row in rows:
        table_row = []
        for field in row:
            table_row.append(field)

        table.add_row(table_row)

    print(table)


async def query_database(
    connection: mysql.connector.MySQLConnection,
    dump: bool,
) -> None:
    cur = connection.cursor()
    cur.execute("SELECT VERSION()")
    row = cur.fetchone()

    db_version: int = 0

    if str(row[0]).startswith("5.7"):
        db_version = 57
    elif str(row[0]).startswith("8.0"):
        db_version = 80
    else:
        raise GracefulExit(f"Unsupported version: {row[0]}")

    if not dump:
        if db_version == 57:
            query = """
                SELECT
                    r.trx_id AS waiting_trx_id,
                    r.trx_mysql_thread_id AS waiting_thread,
                    r.trx_query AS waiting_query,
                    b.trx_id AS blocking_trx_id,
                    b.trx_mysql_thread_id AS blocking_thread,
                    b.trx_query AS blocking_query
                FROM information_schema.INNODB_LOCK_WAITS w
                INNER JOIN information_schema.INNODB_TRX b
                ON b.trx_id = w.blocking_trx_id
                INNER JOIN information_schema.INNODB_TRX r
                ON r.trx_id = w.requesting_trx_id;
            """
        elif db_version == 80:
            query = """
                SELECT
                    r.trx_id waiting_trx_id,
                    r.trx_mysql_thread_id waiting_thread,
                    r.trx_query waiting_query,
                    b.trx_id blocking_trx_id,
                    b.trx_mysql_thread_id blocking_thread,
                    b.trx_query blocking_query
                FROM performance_schema.data_lock_waits w
                INNER JOIN information_schema.innodb_trx b
                ON b.trx_id = w.blocking_engine_transaction_id
                INNER JOIN information_schema.innodb_trx r
                    ON r.trx_id = w.requesting_engine_transaction_id;
            """

        cur.execute(query)
        rows = cur.fetchall()

        table = PrettyTable()
        table.field_names = [
            "waiting_trx_id",
            "waiting_thread",
            "waiting_query",
            "blocking_trx_id",
            "blocking_thread",
            "blocking_query",
        ]

        for row in rows:
            table.add_row(
                [
                    row[0],
                    row[1],
                    row[2],
                    row[3],
                    row[4],
                    row[5],
                ]
            )

        print("Table locks:")
        print(table)

        # Total amount of data and indexes that are currently in use by the InnoDB engine

        print("Data currently in use by the InnoDB engine:")

        query = "SHOW VARIABLES LIKE 'innodb_buffer_pool_size'"
        cur.execute(query)
        row = cur.fetchone()

        innodb_buffer_pool_size = int(row[1]) / (1024**3)

        query = "SELECT SUM(data_length + index_length) / power(1024, 3) FROM information_schema.tables WHERE engine = 'InnoDB'"
        cur.execute(query)
        row = cur.fetchone()

        table = PrettyTable()
        table.field_names = [
            "Total InnoDB Size (GB)",
            "InnoDB Buffer Size (GB)",
        ]

        table.add_row(
            [
                row[0],
                innodb_buffer_pool_size,
            ]
        )

        print(table)

        # Some important global metrics

        if db_version == 57:
            query = "SELECT * FROM information_schema.GLOBAL_STATUS"
        elif db_version == 80:
            query = "SELECT * FROM performance_schema.global_status"

        cur.execute(query)
        rows = cur.fetchall()

        cur.execute(query)
        rows = cur.fetchall()

        global_status = {row[0].upper(): row[1] for row in rows}

        table = PrettyTable()
        table.field_names = [
            "Metric",
            "Value",
        ]

        table.align["Metric"] = "l"
        table.align["Value"] = "r"

        """
        Innodb_buffer_pool_pages_free:
            Should not be zero or close to zero. We should always have free pages available.
            There is a general rule of thumb that it should normally be >= 5% of total pages.
        """

        free_pages_ratio = math.ceil(
            (
                int(global_status.get("INNODB_BUFFER_POOL_PAGES_FREE", 0))
                / int(global_status.get("INNODB_BUFFER_POOL_PAGES_TOTAL", 0))
            )
            * 100
        )

        table.add_row(
            [
                "Buffer pool free page (%, optimal >=%5)",
                free_pages_ratio,
            ]
        )

        """
        Innodb_buffer_pool_wait_free:
            Should not happen. It indicates that a user thread is waiting because it found no free pages to write into.
        """

        table.add_row(
            [
                "Waits for free pages (should not happen)",
                int(global_status.get("INNODB_BUFFER_POOL_WAIT_FREE", 0)),
            ]
        )

        """
        Innodb_buffer_pool_pages_flushed:
            Should be low, or we are flushing too many pages to free pages. Compare it with the number of read pages.
        """

        table.add_row(
            [
                "Buffer pool pages flushed (should be low)",
                int(global_status.get("INNODB_BUFFER_POOL_PAGES_FLUSHED", 0)),
            ]
        )

        """
        Innodb_buffer_pool_reads / Innodb_buffer_pool_read_requests:
            Should be low, or the buffer pool is not preventing enough disk reads.

        """

        read_from_disk_ratio = math.ceil(
            (
                int(global_status.get("INNODB_BUFFER_POOL_READS", 0))
                / int(global_status.get("INNODB_BUFFER_POOL_READ_REQUESTS", 0))
            )
            * 100
        )

        table.add_row(["Read from disk to buffer (%, should be low)", read_from_disk_ratio])

        tables_to_disk_ratio = math.ceil(
            (int(global_status.get("CREATED_TMP_DISK_TABLES", 0)) / int(global_status.get("CREATED_TMP_TABLES", 0)))
            * 100
        )

        table.add_row(["Tmp tables on disk (%, should be low)", tables_to_disk_ratio])

        print("Some important global metrics")
        print(table)

    elif dump:
        # ENGINE INNODB STATUS

        cur.execute("SHOW ENGINE INNODB STATUS")
        row = cur.fetchone()
        print(row[2])

        # PROCESSLIST

        print("Process list:")
        await dump_table(connection, "information_schema", "processlist")

        # INNODB TRX
        print("Innodb Trx:")
        await dump_table(connection, "information_schema", "innodb_trx")

        if db_version == 57:
            # INNODB LOCKS
            print("InnoDB locks:")
            await dump_table(connection, "information_schema", "innodb_locks")

            # INNODB LOCK WAITS
            print("InnoDB lock waits:")
            await dump_table(connection, "information_schema", "innodb_lock_waits")
        elif db_version == 80:
            # DATA LOCKS
            print("Data locks:")
            await dump_table(connection, "performance_schema", "data_locks")

            # DATA LOCK WAITS
            print("Data lock waits:")
            await dump_table(connection, "performance_schema", "data_lock_waits")

        # THREADS
        print("Threads:")
        await dump_table(connection, "performance_schema", "threads")

        # TABLE HANDLES
        print("Table handles:")
        await dump_table(connection, "performance_schema", "table_handles")

        # GLOBAL STAUTS
        print("Global status:")
        await dump_table(connection, "information_schema", "global_status")


def signal_handler(signum: int, frame: Any) -> None:
    raise GracefulExit


signal.signal(signal.SIGINT, signal_handler)


def main(host: str, port: int, user: str, password: str, report: bool) -> None:
    connection = mysql.connector.connect(
        user=user,
        password=password,
        host=host,
        port=port,
    )

    loop = asyncio.new_event_loop()
    loop.run_until_complete(query_database(connection, report))
    loop.close()


@click.command(context_settings=dict(help_option_names=["-?", "--help"]))
@click.option("--host", "-h", prompt="Enter database host")
@click.option("--port", "-P", prompt=False, default=3306)
@click.option("--user", "-u", prompt="Enter database username")
@click.option("--password", "-p", prompt=True, hide_input=True, confirmation_prompt=False)
@click.option(
    "--dump",
    "-d",
    is_flag=True,
    default=False,
    help="Dumps all corresponding tables and InnoDB engine status",
)
def cli(host: str, port: int, user: str, password: str, dump: bool) -> None:
    main(host, port, user, password, dump)


if __name__ == "__main__":
    try:
        cli()
    except GracefulExit as e:
        print(e)
    except Exception as e:
        print(e)
