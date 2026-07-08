int unknown();
void foo228() {

    int x;
    int y;

    x = 0;


        y = unknown();

    while (x < 99) {
       if(y % 2 == 0){
       x = x + 2;
      }
       else{
       x = x + 1;
      }
      }

    /*@ assert (x % 2) == (y % 2); */

  }