int unknown();
/*@ requires i < n; */
void foo193(int i, int n) {

    int b;

    i = 0;


        b = unknown();

    while(i < n && b != 0){
       i = i + 1;
      }

    /*@ assert (b == 0) ==> (i < n); */

  }