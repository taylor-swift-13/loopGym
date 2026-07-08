int unknown();
void foo227() {

    int x;
    int y;

    x = 0;


        y = unknown();

    while (x < 99) {
       if (y % 2 == 0)
       x += 10;
       else
       x -= 5;
      }

    /*@ assert (x % 2) == (y % 2); */

  }